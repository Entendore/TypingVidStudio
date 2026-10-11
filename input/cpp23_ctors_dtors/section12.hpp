#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 12 — THE DOs (Modern Best Practices)
// =============================================================================
namespace section12 {

// --- DO #1: Prefer the Rule of Zero with smart pointers --------------------
class ModernService {
    std::string name_;
    std::vector<int> data_;
    std::unique_ptr<std::string> metadata_; 
public:
    ModernService(std::string n, int size)
        : name_(std::move(n)), data_(size, 0), metadata_(std::make_unique<std::string>("meta")) {}
    // NO custom dtor/copy/move needed. Compiler generates correct ones.
};

// --- DO #2: Use std::make_unique / std::make_shared ------------------------
inline void create_resources() {
    auto p1 = std::make_unique<std::string>("unique"); // Exception-safe, no raw new
    auto p2 = std::make_shared<std::string>("shared");
}

// --- DO #3: Use [[nodiscard]] + std::expected for factories ----------------
// Class-level [[nodiscard]] forces callers to handle the result.
class [[nodiscard]] Connection {
    std::string endpoint_;
    explicit Connection(std::string e) : endpoint_(std::move(e)) {}
public:
    ~Connection() {}

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
    virtual void draw() const {}
};

class Button : public Widget {
public:
    ~Button() override = default;       
    void draw() const override {} // Compiler catches typos like 'drow()'
};

// --- DO #5: Use delegating constructors to share logic --------------------
class Settings {
    std::string profile_;
    int retries_;
    bool debug_;
public:
    Settings(std::string p, int r, bool d)
        : profile_(std::move(p)), retries_(r), debug_(d) {}
    Settings() : Settings("default", 3, false) {}
    explicit Settings(std::string p) : Settings(std::move(p), 5, true) {}
};

// --- DO #6: Use `= default` to explicitly request compiler defaults -------
class TrivialData {
    int x_ = 0;
    int y_ = 0;
public:
    TrivialData() = default;                         
    TrivialData(const TrivialData&) = default;       
    TrivialData(TrivialData&&) noexcept = default;   
    TrivialData& operator=(const TrivialData&) = default;
    TrivialData& operator=(TrivialData&&) noexcept = default;
    ~TrivialData() = default;
};

inline void run() {
    ModernService svc("api", 100);
    create_resources();
    auto ok = Connection::connect("db.example.com");
    if (ok) { /* use */ }
    std::unique_ptr<Widget> w = std::make_unique<Button>();
    w->draw();
    Settings s1;
    TrivialData t1;
}

} // namespace section12
