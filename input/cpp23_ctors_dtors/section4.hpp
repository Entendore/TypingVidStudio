#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 4 — C++23 FACTORY WITH std::expected
// =============================================================================
// Constructors cannot return error codes. The modern C++23 solution: make the
// constructor private and expose a static factory returning std::expected.
namespace section4 {

enum class SessionError { EmptyUser, RequiresTwoFactor };

class SecureSession {
    std::string token_;
    explicit SecureSession(std::string tok) : token_(std::move(tok)) {}
public:
    ~SecureSession() {}

    [[nodiscard]]
    static std::expected<SecureSession, SessionError>
    create(const std::string& user) {
        if (user.empty())
            return std::unexpected(SessionError::EmptyUser);
        if (user == "root")
            return std::unexpected(SessionError::RequiresTwoFactor);
        
        // Implicitly converts to expected<SecureSession, ...>
        return SecureSession("tok_" + user); 
    }
};

inline void run() {
    auto ok = SecureSession::create("alice");
    if (ok) { /* Use ok.value() */ }

    auto fail = SecureSession::create("root");
    if (!fail) { /* Handle fail.error() */ }
}

} // namespace section4
