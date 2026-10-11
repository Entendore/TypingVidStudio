// =============================================================================
// C++23 Constructors & Destructors — Comprehensive Learning Example
// =============================================================================
//
// This file demonstrates:
//   1. Rule of Five (raw resource management)
//   2. = default / = delete (modern idioms)
//   3. Virtual destructors & inheritance order
//   4. C++23 std::expected factory pattern
//   5. C++23 if consteval in constructors
//   6. Delegating constructors (C++11)
//   7. Inheriting constructors (C++11/17)
//   8. Member initialization order gotcha
//   9. Exception safety in constructors
//   10. C++23 explicit(bool) — conditional explicit
//   11. DON'Ts — Common anti-patterns
//   12. DOs — Modern best practices
//
// =============================================================================

// --- Portable logging (C++23 std::println with C++20 fallback) ---------------
#if __has_include(<print>)
    #include <print>
    #define LOG(...) std::println(__VA_ARGS__)
    #define LOGF(fmt, ...) std::print(fmt, __VA_ARGS__)
#else
    #include <iostream>
    #include <format>
    #define LOG(...) std::cout << std::format(__VA_ARGS__) << '\n'
    #define LOGF(fmt, ...) std::cout << std::format(fmt, __VA_ARGS__)
#endif

#include <expected>
#include <string>
#include <utility>
#include <algorithm>
#include <cstddef>
#include <stdexcept>
#include <vector>
#include <memory>
#include <typeinfo>

// Helper: print a pointer address for move-vs-copy visual proof
#define HERE() static_cast<const void*>(this)

// =============================================================================
// SECTION 1 — THE RULE OF FIVE (with memory addresses)
// =============================================================================
// This class owns a raw heap allocation. The compiler-generated defaults would
// do a *shallow* copy → double-free. We MUST define all five special members.
namespace section1 {

class HeapBuffer {
    std::size_t size_;
    int*        data_;

public:
    // 1. Parameterized Constructor
    explicit HeapBuffer(std::size_t n)
        : size_(n), data_(new int[n]{})          // value-initialize to zero
    {
        LOGF("    [Ctor]  {} allocated {} ints\n", HERE(), size_);
    }

    // 2. Destructor — frees the resource
    ~HeapBuffer() {
        LOGF("    [Dtor]  {} freeing {} ints\n", HERE(), size_);
        delete[] data_;
    }

    // 3. Copy Constructor — deep copy
    HeapBuffer(const HeapBuffer& o)
        : size_(o.size_), data_(new int[o.size_])
    {
        std::copy(o.data_, o.data_ + size_, data_);
        LOGF("    [Copy]  {} ← {} ({} ints)\n", HERE(),
             static_cast<const void*>(&o), size_);
    }

    // 4. Copy Assignment — free old, deep copy new (self-assignment safe)
    HeapBuffer& operator=(const HeapBuffer& o) {
        if (this != &o) {
            delete[] data_;
            size_ = o.size_;
            data_ = new int[size_];
            std::copy(o.data_, o.data_ + size_, data_);
            LOGF("    [Copy=] {} ← {} ({} ints)\n", HERE(),
                 static_cast<const void*>(&o), size_);
        }
        return *this;
    }

    // 5. Move Constructor — steal, leave source empty
    //    noexcept is REQUIRED so std::vector will use it during reallocation.
    HeapBuffer(HeapBuffer&& o) noexcept
        : size_(o.size_), data_(o.data_)
    {
        o.data_ = nullptr;
        o.size_ = 0;
        LOGF("    [Move]  {} ← {} (stole {} ints)\n", HERE(),
             static_cast<const void*>(&o), size_);
    }

    // 6. Move Assignment
    HeapBuffer& operator=(HeapBuffer&& o) noexcept {
        if (this != &o) {
            delete[] data_;
            size_ = o.size_;
            data_ = o.data_;
            o.data_ = nullptr;
            o.size_ = 0;
            LOGF("    [Move=] {} ← {} (stole {} ints)\n", HERE(),
                 static_cast<const void*>(&o), size_);
        }
        return *this;
    }

    [[nodiscard]] std::size_t size() const { return size_; }
};

void run() {
    LOG("┌─ Section 1: Rule of Five (addresses prove move vs copy) ──");
    {
        HeapBuffer a(8);
        HeapBuffer b = a;              // copy — different address
        HeapBuffer c = std::move(a);   // move — steals from a
        LOGF("    final: a@{} b@{} c@{}\n", HERE(),
             static_cast<const void*>(&b), static_cast<const void*>(&c));
    }
    LOG("└─\n");
}

} // namespace section1

// =============================================================================
// SECTION 2 — = default / = delete  (Modern Idioms)
// =============================================================================
// Use = delete to forbid operations. Use = default to explicitly request the
// compiler-generated version (better than writing it by hand).
namespace section2 {

class UniqueHandle {
    int fd_;
public:
    explicit UniqueHandle(int fd) : fd_(fd) {
        LOGF("    [Ctor]  acquired fd {}\n", fd_);
    }
    ~UniqueHandle() {
        LOGF("    [Dtor]  closing fd {}\n", fd_);
    }

    // FORBID copying — a file descriptor cannot be shared by value
    UniqueHandle(const UniqueHandle&)            = delete;
    UniqueHandle& operator=(const UniqueHandle&) = delete;

    // ALLOW moving — transfer ownership
    UniqueHandle(UniqueHandle&& o) noexcept : fd_(o.fd_) {
        o.fd_ = -1;
        LOGF("    [Move]  transferred fd {}\n", fd_);
    }
    UniqueHandle& operator=(UniqueHandle&&) noexcept = default;
};

void run() {
    LOG("┌─ Section 2: = delete / = default ─────────────────────");
    {
        UniqueHandle h1(42);
        UniqueHandle h2 = std::move(h1);
        // UniqueHandle h3 = h2;  // ✗ COMPILE ERROR: copy is deleted
    }
    LOG("└─\n");
}

} // namespace section2

// =============================================================================
// SECTION 3 — VIRTUAL DESTRUCTORS & CONSTRUCTION ORDER
// =============================================================================
// KEY RULE: If a class is intended to be a base class, its destructor MUST be
// virtual. Otherwise, `delete basePtr` skips the derived destructor → leak.
//
// Construction order:  Base → Members (declaration order) → Derived body
// Destruction order:   Derived body → Members (reverse) → Base  (exact reverse)
namespace section3 {

class Component {
    std::string name_;
public:
    explicit Component(std::string n) : name_(std::move(n)) {
        LOGF("    [Component Ctor] '{}'\n", name_);
    }
    ~Component() {
        LOGF("    [Component Dtor] '{}'\n", name_);
    }
};

class Entity {
    Component physics_;   // constructed 1st (declared first)
    Component graphics_;  // constructed 2nd
public:
    Entity()
        : physics_("Physics"), graphics_("Graphics")   // member-init order
    {
        LOG("    [Entity Ctor]     body");
    }
    virtual ~Entity() {                                // VIRTUAL!
        LOG("    [Entity Dtor]     body");
    }
};

class Player : public Entity {
    HeapBuffer inventory_;
public:
    Player()
        : Entity(), inventory_(16)                     // Base first, then members
    {
        LOG("    [Player Ctor]     body");
    }
    ~Player() override {
        LOG("    [Player Dtor]     body");
    }
};

void run() {
    LOG("┌─ Section 3: Virtual Dtor & Construction Order ────────");
    {
        LOG("  >> Creating Player via base pointer:");
        Entity* e = new Player();
        LOG("  >> Deleting through base pointer:");
        delete e;   // virtual ~Entity() ensures ~Player() runs first!
    }
    LOG("└─ (notice: construction Base→Derived, destruction Derived→Base)\n");
}

} // namespace section3

// =============================================================================
// SECTION 4 — C++23 FACTORY WITH std::expected
// =============================================================================
// Constructors cannot return error codes. The modern C++23 solution: make the
// constructor private and expose a static factory returning std::expected.
// [[nodiscard]] ensures the caller cannot silently ignore the error.
namespace section4 {

class SecureSession {
    std::string token_;

    explicit SecureSession(std::string tok) : token_(std::move(tok)) {
        LOGF("    [Session Ctor]  token={}\n", token_);
    }
public:
    ~SecureSession() {
        LOGF("    [Session Dtor]  invalidating {}\n", token_);
    }

    [[nodiscard]]
    static std::expected<SecureSession, std::string>
    create(const std::string& user) {
        if (user.empty())
            return std::unexpected("username is empty");
        if (user == "root")
            return std::unexpected("root login requires 2FA");
        return SecureSession("tok_" + user);
    }
};

void run() {
    LOG("┌─ Section 4: C++23 std::expected Factory ──────────────");
    {
        auto ok = SecureSession::create("alice");
        if (ok)  LOG("    ✓ session created");

        auto fail = SecureSession::create("root");
        if (!fail) LOGF("    ✗ rejected: {}\n", fail.error());
    }
    LOG("└─\n");
}

} // namespace section4

// =============================================================================
// SECTION 5 — C++23 `if consteval` IN A CONSTRUCTOR
// =============================================================================
// `if consteval` (C++23) lets a constructor behave differently at compile time
// vs. run time. Here we enforce a range check at compile time when possible.
namespace section5 {

struct BoundedValue {
    int value;

    consteval static int check(int v) {
        if (v < 0 || v > 100)
            throw "BoundedValue out of range [0,100]";   // compile-time error
        return v;
    }

    constexpr BoundedValue(int v) : value(v) {
        if consteval {
            // Compile-time path: validate immediately (constexpr context)
            value = check(v);
        } else {
            // Run-time path: throw a normal exception
            if (v < 0 || v > 100)
                throw std::out_of_range("BoundedValue out of [0,100]");
        }
    }

    ~BoundedValue() = default;   // explicit = default is good documentation
};

void run() {
    LOG("┌─ Section 5: C++23 if consteval ───────────────────────");
    {
        constexpr BoundedValue compile_time{50};   // OK, checked at compile time
        LOGF("    compile-time value: {}\n", compile_time.value);

        try {
            BoundedValue runtime_val{150};         // throws at runtime
        } catch (const std::out_of_range& e) {
            LOGF("    runtime caught: {}\n", e.what());
        }

        // constexpr BoundedValue bad{200};        // ✗ COMPILE ERROR!
    }
    LOG("└─\n");
}

} // namespace section5

// =============================================================================
// SECTION 6 — DELEGATING CONSTRUCTORS (C++11)
// =============================================================================
// A constructor can call another constructor of the SAME class via the
// initializer list. This eliminates duplicated init logic.
namespace section6 {

class Config {
    std::string name_;
    int         timeout_;
    bool        verbose_;

public:
    // "Master" constructor — does all the real work
    Config(std::string name, int timeout, bool verbose)
        : name_(std::move(name)), timeout_(timeout), verbose_(verbose)
    {
        LOGF("    [Config master] name={} timeout={} verbose={}\n",
             name_, timeout_, verbose_);
    }

    // Delegating: calls the master with defaults
    Config() : Config("default", 3000, false) {
        LOG("    [Config default] delegated to master");
    }

    // Delegating: calls the master with one override
    explicit Config(std::string name) : Config(std::move(name), 5000, true) {
        LOGF("    [Config name-only] delegated with name={}\n", name_);
    }

    ~Config() {
        LOGF("    [Config Dtor] {}\n", name_);
    }
};

void run() {
    LOG("┌─ Section 6: Delegating Constructors ──────────────────");
    {
        Config c1;                  // delegates to master
        Config c2("prod");          // delegates to master
        Config c3("dev", 1000, false);  // master directly
    }
    LOG("└─\n");
}

} // namespace section6

// =============================================================================
// SECTION 7 — INHERITING CONSTRUCTORS (C++11/17)
// =============================================================================
// `using Base::Base;` makes the derived class inherit all base constructors.
// C++17 improved this: inherited ctors now initialize derived members with
// their default member initializers.
namespace section7 {

class Shape {
protected:
    std::string color_;
public:
    Shape() : color_("black") {
        LOGF("    [Shape Ctor] color={}\n", color_);
    }
    explicit Shape(std::string c) : color_(std::move(c)) {
        LOGF("    [Shape Ctor] color={}\n", color_);
    }
    virtual ~Shape() {
        LOGF("    [Shape Dtor] color={}\n", color_);
    }
};

class Circle : public Shape {
    double radius_ = 1.0;   // default member initializer (C++17 inherits this!)
public:
    using Shape::Shape;     // INHERIT all Shape constructors

    ~Circle() override {
        LOGF("    [Circle Dtor] radius={}\n", radius_);
    }

    void describe() const {
        LOGF("    Circle: color={} radius={}\n", color_, radius_);
    }
};

void run() {
    LOG("┌─ Section 7: Inheriting Constructors ──────────────────");
    {
        Circle c1;              // inherited default ctor
        Circle c2("red");       // inherited Shape(string) ctor
        c1.describe();
        c2.describe();
    }
    LOG("└─\n");
}

} // namespace section7

// =============================================================================
// SECTION 8 — MEMBER INITIALIZATION ORDER GOTCHA
// =============================================================================
// KEY RULE: Members are initialized in DECLARATION ORDER, regardless of the
// order you write them in the initializer list. Compilers warn with -Wreorder.
// This is one of the most common C++ bugs.
namespace section8 {

class Rectangle {
    int width_;
    int height_;
    int area_;      // ← declared AFTER width_ and height_

public:
    // INTENTIONAL BUG: initializer list puts area_ first.
    // The compiler will actually initialize width_, then height_, then area_
    // — so area_ reads UNINITIALIZED width_ and height_!
    //
    // With -Wreorder, you'll see a warning.
    Rectangle(int w, int h)
        : area_(w * h),     // ← BUG: area_ is initialized 3rd, not 1st
          width_(w),
          height_(h)
    {
        // By the time the body runs, area_ has garbage. Recompute it correctly.
        area_ = width_ * height_;
        LOGF("    [Rect Ctor] {}x{} area={}\n", width_, height_, area_);
    }

    ~Rectangle() = default;

    // Correct version (no warning):
    // Rectangle(int w, int h) : width_(w), height_(h), area_(w*h) { ... }
};

void run() {
    LOG("┌─ Section 8: Member Init Order Gotcha ─────────────────");
    LOG("    Members init in DECLARATION order, not initializer-list order.");
    LOG("    Compile with -Wreorder to catch this bug.");
    {
        Rectangle r(10, 5);
    }
    LOG("└─\n");
}

} // namespace section8

// =============================================================================
// SECTION 9 — EXCEPTION SAFETY IN CONSTRUCTORS
// =============================================================================
// If a constructor throws, any members that were ALREADY constructed are
// automatically destroyed in reverse order. The object itself is NOT created.
// This is why RAII members are so important — they clean themselves up.
namespace section9 {

class LeakyResource {
    int id_;
public:
    explicit LeakyResource(int id) : id_(id) {
        LOGF("    [Leaky {}] acquired\n", id_);
    }
    ~LeakyResource() {
        LOGF("    [Leaky {}] released\n", id_);
    }
};

class RiskyConstructor {
    LeakyResource r1_;
    LeakyResource r2_;
    LeakyResource r3_;   // this one will throw

public:
    RiskyConstructor()
        : r1_(1), r2_(2), r3_(3)
    {
        LOG("    [Risky] body — about to throw");
        throw std::runtime_error("simulated failure in constructor body");
    }
    ~RiskyConstructor() {
        LOG("    [Risky Dtor] — THIS NEVER RUNS (object never fully created)");
    }
};

void run() {
    LOG("┌─ Section 9: Exception Safety in Constructors ─────────");
    LOG("    Members already constructed are destroyed if ctor throws.");
    LOG("    The object's own destructor does NOT run.");
    try {
        RiskyConstructor rc;
    } catch (const std::exception& e) {
        LOGF("    caught: {}\n", e.what());
    }
    LOG("    ↑ Notice: r1 and r2 were cleaned up, r3 was never constructed,");
    LOG("      and ~RiskyConstructor never ran.\n");
    LOG("└─\n");
}

} // namespace section9

// =============================================================================
// SECTION 10 — C++23 explicit(bool) — CONDITIONAL EXPLICIT
// =============================================================================
// C++23 lets a constructor be explicit ONLY when a compile-time condition
// is true. This is incredibly useful for template classes.
namespace section10 {

// A wrapper that is implicit when T is small, explicit when T is large.
template<typename T>
class Wrapper {
    T value_;
public:
    // explicit(true)  when sizeof(T) > 4  → must write Wrapper<T>{x}
    // explicit(false) when sizeof(T) <= 4 → can write Wrapper<T> w = x
    explicit(sizeof(T) > 4) Wrapper(T v) : value_(v) {
        LOGF("    [Wrapper<{}>] constructed (sizeof={} explicit={})\n",
             typeid(T).name(), sizeof(T), (sizeof(T) > 4));
    }

    T get() const { return value_; }
    ~Wrapper() = default;
};

void run() {
    LOG("┌─ Section 10: C++23 explicit(bool) ────────────────────");
    LOG("    Constructor is explicit only when sizeof(T) > 4.");
    {
        // int is 4 bytes → implicit conversion allowed
        Wrapper<int> w1 = 42;
        LOGF("    w1 = {} (implicit OK)\n", w1.get());

        // double is 8 bytes → implicit conversion FORBIDDEN
        // Wrapper<double> w2 = 3.14;   // ✗ COMPILE ERROR: explicit(sizeof>4)
        Wrapper<double> w3{3.14};       // ✓ direct initialization works
        LOGF("    w3 = {} (direct init)\n", w3.get());
    }
    LOG("└─\n");
}

} // namespace section10

// =============================================================================
// SECTION 11 — THE DON'Ts (Anti-Patterns)
// =============================================================================
// Each sub-example demonstrates a common mistake.
namespace section11 {

// --- DON'T #1: Call virtual functions from constructors/destructors ---------
// Virtual dispatch in a ctor/dtor resolves to the CURRENT class, not the
// most-derived class. This is a classic source of bugs.
class Base {
public:
    Base() {
        LOG("    [Base Ctor] calling describe()...");
        describe();   // ← SURPRISE: calls Base::describe, NOT Derived::describe!
    }
    virtual void describe() const { LOG("    → Base::describe"); }
    virtual ~Base() {
        LOG("    [Base Dtor] calling describe()...");
        describe();   // ← Same issue in dtor
    }
};

class Derived : public Base {
    std::string data_ = "derived-data";
public:
    Derived() { LOG("    [Derived Ctor]"); }
    void describe() const override {
        // If called from Base ctor, data_ is NOT YET initialized!
        // If called from Base dtor, data_ is ALREADY destroyed!
        LOGF("    → Derived::describe (data={})\n", data_);
    }
    ~Derived() override { LOG("    [Derived Dtor]"); }
};

// --- DON'T #2: Throw from a destructor --------------------------------------
// If a destructor throws during stack unwinding (another exception active),
// std::terminate is called. Even without that, it's almost always wrong.
class BadDtor {
public:
    ~BadDtor() noexcept(false) {
        // LOG("    [BadDtor] about to throw — DON'T DO THIS");
        // throw std::runtime_error("dtor failure");   // ← NEVER DO THIS
    }
};

// --- DON'T #3: Forget noexcept on move operations ---------------------------
// Without noexcept, std::vector falls back to COPY during reallocation,
// killing performance and potentially breaking exception guarantees.
class SlowMove {
    std::vector<int> data_;
public:
    explicit SlowMove(int n) : data_(n, 42) {}
    // Missing noexcept! std::vector will COPY, not MOVE, on reallocation.
    SlowMove(SlowMove&& o) /* ← no noexcept! */ : data_(std::move(o.data_)) {}
    SlowMove(const SlowMove&) = default;
    SlowMove& operator=(SlowMove&&) /* ← no noexcept! */ = default;
    SlowMove& operator=(const SlowMove&) = default;
};

// --- DON'T #4: Forget explicit on single-argument constructors -------------
// Implicit conversions create subtle bugs.
class Money {
    double amount_;
public:
    Money(double a) : amount_(a) {}   // ← NOT explicit!
    // Now: Money m = 100; compiles. Is that $100? 100 cents? 100 euros?
    // And: void pay(Money); pay(50); compiles — accidental conversion!
};

// --- DON'T #5: Forget to reset moved-from state -----------------------------
class UnsafeMove {
    int* data_;
public:
    explicit UnsafeMove(int n) : data_(new int[n]) {}
    ~UnsafeMove() { delete[] data_; }
    UnsafeMove(UnsafeMove&& o) noexcept : data_(o.data_) {
        // ← BUG: forgot to null out o.data_. Both destructors will delete
        // the same pointer → double-free crash!
    }
    UnsafeMove(const UnsafeMove&) = delete;
    UnsafeMove& operator=(UnsafeMove&&) = delete;
    UnsafeMove& operator=(const UnsafeMove&) = delete;
};

void run() {
    LOG("╔════════════════════════════════════════════════════════╗");
    LOG("║  Section 11: THE DON'Ts (Anti-Patterns)              ║");
    LOG("╚════════════════════════════════════════════════════════╝");

    LOG("\n  ✗ DON'T #1: Call virtual functions from ctors/dtors");
    LOG("    ─────────────────────────────────────────────────────");
    {
        LOG("    Creating Derived (watch describe() output):");
        Derived d;
        LOG("    ↑ Notice: Base ctor called Base::describe, not Derived::describe.");
        LOG("      This is because during Base's ctor, the Derived part doesn't exist yet.");
    }

    LOG("\n  ✗ DON'T #2: Throw from destructors");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    Code: ~BadDtor() noexcept(false) { throw ...; }");
    LOG("    → If thrown during stack unwinding, std::terminate kills the program.");
    LOG("    → Even alone, it makes RAII impossible. NEVER throw from dtors.");

    LOG("\n  ✗ DON'T #3: Forget noexcept on move operations");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    Code: SlowMove(SlowMove&& o)  // missing noexcept");
    LOG("    → std::vector will COPY instead of MOVE during reallocation.");
    LOG("    → Massive performance loss and potential exception-safety issues.");

    LOG("\n  ✗ DON'T #4: Forget explicit on single-arg constructors");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    Code: Money(double a);   // not explicit");
    LOG("    → Money m = 100; compiles silently.");
    LOG("    → pay(50); compiles — accidental conversion from int to Money!");
    LOG("    → Fix: explicit Money(double a);");

    LOG("\n  ✗ DON'T #5: Forget to reset moved-from state");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    Code: UnsafeMove(UnsafeMove&& o) : data_(o.data_) {}");
    LOG("    → o.data_ still points to the stolen memory.");
    LOG("    → Both destructors call delete[] on the same pointer → DOUBLE FREE.");
    LOG("    → Fix: always set o.data_ = nullptr after stealing.");

    LOG("\n  ✗ DON'T #6: Initialize members out of declaration order");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    → See Section 8. Members init in DECLARATION order, always.");

    LOG("\n  ✗ DON'T #7: Use raw new/delete when smart pointers work");
    LOG("    ─────────────────────────────────────────────────────");
    LOG("    → See Section 12 DO #1 for the modern alternative.");
    LOG("");
}

} // namespace section11

// =============================================================================
// SECTION 12 — THE DOs (Modern Best Practices)
// =============================================================================
namespace section12 {

// --- DO #1: Prefer the Rule of Zero with smart pointers --------------------
// If you don't manage raw resources, you don't need ANY special members.
// The compiler-generated ones do the right thing automatically.
class ModernService {
    std::string name_;
    std::vector<int> data_;
    std::unique_ptr<std::string> metadata_;   // smart pointer — auto-cleanup
public:
    ModernService(std::string n, int size)
        : name_(std::move(n))
        , data_(size, 0)
        , metadata_(std::make_unique<std::string>("meta"))
    {}
    // NO destructor, NO copy/move — compiler generates correct ones!
    // This is the "Rule of Zero" — prefer it whenever possible.
};

// --- DO #2: Use std::make_unique / std::make_shared ------------------------
// Single allocation, exception-safe, no raw `new`.
void create_resources() {
    auto p1 = std::make_unique<std::string>("unique");     // ✓ DO
    auto p2 = std::make_shared<std::string>("shared");     // ✓ DO
    // std::string* raw = new std::string("bad");          // ✗ DON'T
    LOGF("    created: {} and {}\n", *p1, *p2);
}

// --- DO #3: Use [[nodiscard]] on factory methods ---------------------------
// Forces callers to handle the result — no silent failures.
class [[nodiscard]] Connection {
    std::string endpoint_;
    explicit Connection(std::string e) : endpoint_(std::move(e)) {}
public:
    ~Connection() { LOGF("    [Connection Dtor] {}\n", endpoint_); }

    [[nodiscard]]
    static std::expected<Connection, std::string> connect(const std::string& host) {
        if (host.empty()) return std::unexpected("empty host");
        return Connection(host);
    }
};

// --- DO #4: Use `override` on all virtual function overrides ---------------
class Widget {
public:
    virtual ~Widget() = default;
    virtual void draw() const { LOG("    Widget::draw"); }
};

class Button : public Widget {
public:
    ~Button() override = default;       // ← override on dtor
    void draw() const override {        // ← override on method
        LOG("    Button::draw");
    }
    // If you typo `draw` as `drow`, the compiler catches it thanks to override.
};

// --- DO #5: Use delegating constructors to share logic --------------------
class Settings {
    std::string profile_;
    int retries_;
    bool debug_;
public:
    // Master ctor
    Settings(std::string p, int r, bool d)
        : profile_(std::move(p)), retries_(r), debug_(d) {
        LOGF("    [Settings] profile={} retries={} debug={}\n",
             profile_, retries_, debug_);
    }
    // Delegating — no duplication
    Settings() : Settings("default", 3, false) {}
    explicit Settings(std::string p) : Settings(std::move(p), 5, true) {}
};

// --- DO #6: Use `= default` to explicitly request compiler defaults -------
class TrivialData {
    int x_ = 0;
    int y_ = 0;
public:
    TrivialData() = default;                         // explicit default
    TrivialData(const TrivialData&) = default;       // explicit copy
    TrivialData(TrivialData&&) noexcept = default;   // explicit move
    TrivialData& operator=(const TrivialData&) = default;
    TrivialData& operator=(TrivialData&&) noexcept = default;
    ~TrivialData() = default;
    // Clearer than writing them by hand; documents intent.
};

void run() {
    LOG("╔════════════════════════════════════════════════════════╗");
    LOG("║  Section 12: THE DOs (Modern Best Practices)         ║");
    LOG("╚════════════════════════════════════════════════════════╝");

    LOG("\n  ✓ DO #1: Prefer the Rule of Zero with smart pointers");
    LOG("    ─────────────────────────────────────────────────────");
    {
        ModernService svc("api", 100);
        LOG("    → No custom dtor, copy, or move needed. Compiler handles it.");
    }

    LOG("\n  ✓ DO #2: Use std::make_unique / std::make_shared");
    LOG("    ─────────────────────────────────────────────────────");
    create_resources();

    LOG("\n  ✓ DO #3: Use [[nodiscard]] + std::expected for factories");
    LOG("    ─────────────────────────────────────────────────────");
    {
        auto ok = Connection::connect("db.example.com");
        if (ok) LOG("    ✓ connected");

        auto fail = Connection::connect("");
        if (!fail) LOGF("    ✗ rejected: {}\n", fail.error());
        // [[nodiscard]] would warn if we wrote: Connection::connect("x");
    }

    LOG("\n  ✓ DO #4: Always use `override` on virtual overrides");
    LOG("    ─────────────────────────────────────────────────────");
    {
        std::unique_ptr<Widget> w = std::make_unique<Button>();
        w->draw();   // Correctly dispatches to Button::draw
    }

    LOG("\n  ✓ DO #5: Use delegating constructors to share logic");
    LOG("    ─────────────────────────────────────────────────────");
    {
        Settings s1;
        Settings s2("prod");
        Settings s3("test", 10, false);
    }

    LOG("\n  ✓ DO #6: Use `= default` to document intent");
    LOG("    ─────────────────────────────────────────────────────");
    {
        TrivialData t1;
        TrivialData t2 = t1;
        LOG("    → Explicit = default is clearer than hand-written equivalents.");
    }
    LOG("");
}

} // namespace section12

// =============================================================================
// MAIN — Run all sections
// =============================================================================
int main() {
    LOG("╔══════════════════════════════════════════════════════╗");
    LOG("║  C++23 Constructors & Destructors — Full Demo      ║");
    LOG("╚══════════════════════════════════════════════════════╝\n");

    section1::run();
    section2::run();
    section3::run();
    section4::run();
    section5::run();
    section6::run();
    section7::run();
    section8::run();
    section9::run();
    section10::run();
    section11::run();
    section12::run();

    LOG("=== Done. All destructors fired automatically. ===");
}
