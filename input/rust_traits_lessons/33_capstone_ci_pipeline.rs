// ============================================================================
// LESSON 33 - CAPSTONE 3: A CI Pipeline Runner
// ============================================================================
// The final weave - nearly every lesson in one program:
//   * supertrait Step: Display        (09) - every step is loggable
//   * default method run_with_retries (02) - free retry policy for all
//   * closures stored as steps        (18) - Box<dyn FnMut> (05 too)
//   * Vec<Box<dyn Step + Send>>       (05, 23) - mixed, thread-movable steps
//   * associated const DEFAULT_RETRIES(08, 29)
//   * TRAIT UPCASTING                 (28) - &dyn Step -> &dyn Display
//   * iterator adapter over failures  (11)
//   * Display for the report          (06)
//
// Requires Rust 1.86+ (upcasting). Pre-1.86: swap the marked lines for the
// as_display() workaround from lesson 28.
//
// Run me:  rustc --edition 2021 33_capstone_ci_pipeline.rs && ./33_capstone_ci_pipeline
// ============================================================================

use std::fmt;
use std::time::Duration;

// ---- the core abstraction --------------------------------------------------
// Every Step IS Display, so logging never needs a special case.
trait Step: fmt::Display {
    fn run(&mut self) -> Result<Duration, String>;

    // Default retry policy - every implementor gets it free (lesson 02).
    fn run_with_retries(&mut self, attempts: u32) -> Result<Duration, String> {
        let mut last_err = String::new();
        for attempt in 1..=attempts {
            match self.run() {
                Ok(d) => return Ok(d),
                Err(e) => {
                    println!("     attempt {}/{} failed: {}", attempt, attempts, e);
                    last_err = e;
                }
            }
        }
        Err(last_err)
    }
}

// ---- step 1 type: a simulated shell command --------------------------------
struct ShellStep {
    name: &'static str,
    cmd: &'static str,
    fails: bool,
}

impl fmt::Display for ShellStep {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "shell:{} ({})", self.name, self.cmd)
    }
}

impl Step for ShellStep {
    fn run(&mut self) -> Result<Duration, String> {
        if self.fails {
            Err(format!("`{}` exited non-zero", self.cmd))
        } else {
            Ok(Duration::from_millis(120))
        }
    }
}

// ---- step 2 type: flaky infrastructure (for retry demo) --------------------
struct FlakyStep {
    name: &'static str,
    attempt: u32,
    succeed_on: u32,
}

impl fmt::Display for FlakyStep {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "flaky:{}", self.name)
    }
}

impl Step for FlakyStep {
    fn run(&mut self) -> Result<Duration, String> {
        self.attempt += 1;
        if self.attempt >= self.succeed_on {
            Ok(Duration::from_millis(40))
        } else {
            Err("network hiccup".to_string())
        }
    }
}

// ---- step 3 type: behavior supplied by a CLOSURE (lesson 18) ---------------
struct ClosureStep {
    name: &'static str,
    f: Box<dyn FnMut() -> Result<(), String> + Send>,
}

impl fmt::Display for ClosureStep {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "closure:{}", self.name)
    }
}

impl Step for ClosureStep {
    fn run(&mut self) -> Result<Duration, String> {
        (self.f)().map(|_| Duration::from_millis(15))
    }
}

// ---- the pipeline: mixed steps behind trait objects -------------------------
struct Pipeline {
    name: &'static str,
    steps: Vec<Box<dyn Step + Send>>, // + Send: safe to hand to a thread pool
}

impl Pipeline {
    const DEFAULT_RETRIES: u32 = 3; // associated const (lessons 08, 29)

    fn new(name: &'static str) -> Self {
        Pipeline { name, steps: Vec::new() }
    }

    fn add(&mut self, step: Box<dyn Step + Send>) {
        self.steps.push(step);
    }

    fn run(&mut self, retries: u32) -> PipelineReport {
        let mut reports = Vec::new();
        for step in self.steps.iter_mut() {
            // UPCASTING PAYOFF (lesson 28): one object, two dyn views.
            let s: &dyn Step = step.as_ref(); // drop the + Send auto trait
            let d: &dyn fmt::Display = s;     // upcast to the supertrait!
            println!(">> {}", d);
            // Pre-1.86 alternative: add `fn as_display(&self) -> &dyn Display`
            // to Step (default body `self`) and call step.as_display().

            let status = step.run_with_retries(retries);
            match &status {
                Ok(d) => println!("   ok in {:?}", d),
                Err(e) => println!("   FAILED: {}", e),
            }
            reports.push(StepReport { step: s.to_string(), status });
        }
        PipelineReport { pipeline: self.name, steps: reports }
    }
}

// ---- the report: plain data + iterator + Display ----------------------------
struct StepReport {
    step: String,
    status: Result<Duration, String>,
}

struct PipelineReport {
    pipeline: &'static str,
    steps: Vec<StepReport>,
}

impl PipelineReport {
    // Iterator adapter over failures (lesson 11):
    fn failures(&self) -> impl Iterator<Item = &StepReport> + '_ {
        self.steps.iter().filter(|r| r.status.is_err())
    }
}

impl fmt::Display for PipelineReport {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "=== {} report ===", self.pipeline)?;
        for s in &self.steps {
            match &s.status {
                Ok(d) => writeln!(f, "  PASS  {:<34} {:?}", s.step, d)?,
                Err(e) => writeln!(f, "  FAIL  {:<34} {}", s.step, e)?,
            }
        }
        let total: u128 = self
            .steps
            .iter()
            .filter_map(|s| s.status.as_ref().ok())
            .map(|d| d.as_millis())
            .sum();
        write!(
            f,
            "  total: {} ms across {} failures",
            total,
            self.failures().count()
        )
    }
}

fn main() {
    let mut pipe = Pipeline::new("build-and-test");

    pipe.add(Box::new(ShellStep { name: "checkout", cmd: "git clone origin", fails: false }));
    pipe.add(Box::new(ShellStep { name: "build", cmd: "cargo build --release", fails: false }));
    pipe.add(Box::new(FlakyStep { name: "integration tests", attempt: 0, succeed_on: 3 }));
    pipe.add(Box::new(ClosureStep {
        name: "deploy staging",
        f: Box::new(|| {
            println!("     (deploying to staging...)");
            Ok(())
        }),
    }));
    pipe.add(Box::new(ShellStep { name: "push prod", cmd: "kubectl apply", fails: true }));

    let report = pipe.run(Pipeline::DEFAULT_RETRIES);
    println!("\n{}", report);

    // Downstream consumers only need the report - iterate its failures:
    let critical: Vec<&str> = report
        .failures()
        .map(|r| r.step.as_str())
        .collect();
    println!("pages on-call for: {:?}", critical);
}
