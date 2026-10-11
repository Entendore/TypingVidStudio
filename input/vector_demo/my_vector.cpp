// my_vector.cpp
// ---------------------------------------------------------------------------
// A from-scratch, std::vector-like container plus a demo, all in one file.
//
// Ideas demonstrated:
//   * raw heap memory + placement new (separating allocation from construction)
//   * size vs. capacity, and the doubling growth strategy that makes
//     push_back amortized O(1)
//   * the Rule of Five: destructor, copy ctor, move ctor, copy assign, move assign
//   * move semantics ("stealing" the buffer instead of copying it)
//   * iterators as plain pointers
//   * basic exception safety in the reallocation path
//   * observing object lifetimes with an instrumented type
//
// Build:
//   g++ -std=c++17 -Wall -Wextra -Wpedantic -O0 -g my_vector.cpp -o my_vector
// Run:
//   ./my_vector
// ---------------------------------------------------------------------------

#include <cassert>
#include <cstddef>
#include <initializer_list>
#include <iostream>
#include <new>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

// ===========================================================================
// PART 1: MyVector<T>
// ===========================================================================

template <typename T>
class MyVector {
public:
    // STL-style type aliases.
    using value_type      = T;
    using size_type       = std::size_t;
    using difference_type = std::ptrdiff_t;
    using reference       = T&;
    using const_reference = const T&;
    using pointer         = T*;
    using const_pointer   = const T*;
    using iterator        = T*;          // our iterators are just pointers
    using const_iterator  = const T*;

    // ---------------------------- construction ----------------------------

    MyVector() noexcept = default;

    // MyVector<int> v(5);  -> five value-initialized ints
    explicit MyVector(size_type count) {
        reserve(count);
        for (size_type i = 0; i < count; ++i) new (m_data + i) T();
        m_size = count;
    }

    // MyVector<int> v(5, 42);  -> five 42s
    MyVector(size_type count, const T& value) {
        reserve(count);
        for (size_type i = 0; i < count; ++i) new (m_data + i) T(value);
        m_size = count;
    }

    // MyVector<int> v{1, 2, 3};
    MyVector(std::initializer_list<T> init) {
        reserve(init.size());
        for (const T& v : init) push_back(v);
    }

    // Copy constructor: allocate a fresh buffer and copy every element.
    MyVector(const MyVector& other) {
        reserve(other.m_size);
        for (size_type i = 0; i < other.m_size; ++i)
            new (m_data + i) T(other.m_data[i]);
        m_size = other.m_size;
    }

    // Move constructor: steal the pointer. O(1), never throws.
    MyVector(MyVector&& other) noexcept
        : m_data(other.m_data),
          m_size(other.m_size),
          m_capacity(other.m_capacity) {
        other.m_data     = nullptr;
        other.m_size     = 0;
        other.m_capacity = 0;
    }

    // Copy assignment via copy-and-swap: strong exception guarantee.
    MyVector& operator=(const MyVector& other) {
        if (this != &other) {
            MyVector tmp(other);   // may throw; *this is untouched
            swap(tmp);
        }
        return *this;
    }

    // Move assignment: free what we have, then steal.
    MyVector& operator=(MyVector&& other) noexcept {
        if (this != &other) {
            destroyAll();
            m_data           = other.m_data;
            m_size           = other.m_size;
            m_capacity       = other.m_capacity;
            other.m_data     = nullptr;
            other.m_size     = 0;
            other.m_capacity = 0;
        }
        return *this;
    }

    ~MyVector() { destroyAll(); }

    // --------------------------- element access ---------------------------

    reference       operator[](size_type i)       noexcept { return m_data[i]; }
    const_reference operator[](size_type i) const noexcept { return m_data[i]; }

    reference at(size_type i) {
        if (i >= m_size) throw std::out_of_range("MyVector::at: index out of range");
        return m_data[i];
    }
    const_reference at(size_type i) const {
        if (i >= m_size) throw std::out_of_range("MyVector::at: index out of range");
        return m_data[i];
    }

    reference       front()       noexcept { return m_data[0]; }
    const_reference front() const noexcept { return m_data[0]; }
    reference       back()        noexcept { return m_data[m_size - 1]; }
    const_reference back()  const noexcept { return m_data[m_size - 1]; }

    pointer       data()       noexcept { return m_data; }
    const_pointer data() const noexcept { return m_data; }

    // ------------------------------ iterators -----------------------------

    iterator       begin()        noexcept { return m_data; }
    iterator       end()          noexcept { return m_data + m_size; }
    const_iterator begin()  const noexcept { return m_data; }
    const_iterator end()    const noexcept { return m_data + m_size; }
    const_iterator cbegin() const noexcept { return m_data; }
    const_iterator cend()   const noexcept { return m_data + m_size; }

    // ------------------------------ capacity ------------------------------

    bool      empty()    const noexcept { return m_size == 0; }
    size_type size()     const noexcept { return m_size; }
    size_type capacity() const noexcept { return m_capacity; }

    // Grow the buffer *without* changing the number of elements.
    void reserve(size_type newCapacity) {
        if (newCapacity > m_capacity) reallocate(newCapacity);
    }

    void shrink_to_fit() {
        if (m_size != m_capacity) reallocate(m_size);
    }

    // ------------------------------ modifiers -----------------------------

    void clear() noexcept {
        for (size_type i = 0; i < m_size; ++i) m_data[i].~T();
        m_size = 0;                       // capacity is intentionally kept
    }

    void push_back(const T& value) { emplace_back(value); }
    void push_back(T&& value)      { emplace_back(std::move(value)); }

    // Construct the new element in place -- no temporary, no extra copy.
    template <typename... Args>
    reference emplace_back(Args&&... args) {
        if (m_size == m_capacity) grow();
        new (m_data + m_size) T(std::forward<Args>(args)...);
        return m_data[m_size++];
    }

    void pop_back() {
        // Just like std::vector, calling this on an empty vector is a bug.
        m_data[--m_size].~T();
    }

    void resize(size_type newSize, const T& value = T()) {
        if (newSize < m_size) {
            for (size_type i = newSize; i < m_size; ++i) m_data[i].~T();
        } else if (newSize > m_size) {
            reserve(newSize);
            for (size_type i = m_size; i < newSize; ++i) new (m_data + i) T(value);
        }
        m_size = newSize;
    }

    // Simplified insert/erase (std::vector's real versions handle ranges and
    // are much more careful about exception safety).
    //
    // `value` is taken by value on purpose: that copy stays valid even if
    // push_back reallocates the buffer.
    iterator insert(const_iterator pos, T value) {
        size_type index = static_cast<size_type>(pos - m_data);
        push_back(value);                                  // make room at the end
        for (size_type i = m_size - 1; i > index; --i)     // shift right
            m_data[i] = std::move(m_data[i - 1]);
        m_data[index] = value;
        return m_data + index;
    }

    iterator erase(const_iterator pos) {
        size_type index = static_cast<size_type>(pos - m_data);
        for (size_type i = index; i + 1 < m_size; ++i)     // shift left
            m_data[i] = std::move(m_data[i + 1]);
        pop_back();
        return m_data + index;
    }

    void swap(MyVector& other) noexcept {
        std::swap(m_data,     other.m_data);
        std::swap(m_size,     other.m_size);
        std::swap(m_capacity, other.m_capacity);
    }

private:
    // Raw memory: no T is constructed here yet.
    static pointer allocate(size_type n) {
        return static_cast<pointer>(::operator new(n * sizeof(T)));
    }

    // Growth policy: 0 -> 1 -> 2 -> 4 -> 8 ...
    // Doubling is what makes push_back amortized O(1).
    void grow() {
        reallocate(m_capacity == 0 ? 1 : m_capacity * 2);
    }

    // Allocate a new buffer, move the elements over, free the old one.
    void reallocate(size_type newCapacity) {
        pointer   newData     = newCapacity ? allocate(newCapacity) : nullptr;
        size_type constructed = 0;

        try {
            for (; constructed < m_size; ++constructed)
                new (newData + constructed) T(std::move_if_noexcept(m_data[constructed]));
        } catch (...) {                       // roll back if a ctor throws
            for (size_type i = 0; i < constructed; ++i) newData[i].~T();
            ::operator delete(newData);
            throw;
        }

        destroyAll();
        m_data     = newData;
        m_size     = constructed;
        m_capacity = newCapacity;
    }

    // Destroy every element and release the buffer.
    void destroyAll() noexcept {
        for (size_type i = 0; i < m_size; ++i) m_data[i].~T();
        ::operator delete(m_data);            // fine even if m_data == nullptr
        m_data     = nullptr;
        m_size     = 0;
        m_capacity = 0;
    }

    pointer   m_data     = nullptr;
    size_type m_size     = 0;
    size_type m_capacity = 0;
};

// Free-function swap and comparisons, so the type behaves like a real container.
template <typename T>
void swap(MyVector<T>& a, MyVector<T>& b) noexcept { a.swap(b); }

template <typename T>
bool operator==(const MyVector<T>& a, const MyVector<T>& b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (!(a[i] == b[i])) return false;
    return true;
}

template <typename T>
bool operator!=(const MyVector<T>& a, const MyVector<T>& b) { return !(a == b); }

// ===========================================================================
// PART 2: Demo
// ===========================================================================

// ---------------------------------------------------------------------------
// An instrumented type so we can *watch* objects being constructed, copied,
// moved and destroyed. If anything leaks, Tracker::alive won't return to 0.
// ---------------------------------------------------------------------------
struct Tracker {
    static int alive;

    std::string name;

    explicit Tracker(std::string n = "?") : name(std::move(n)) {
        ++alive;
        std::cout << "      ctor  " << name << "   (alive=" << alive << ")\n";
    }
    Tracker(const Tracker& o) : name(o.name) {
        ++alive;
        std::cout << "      copy  " << name << "   (alive=" << alive << ")\n";
    }
    Tracker(Tracker&& o) noexcept : name(std::move(o.name)) {
        ++alive;
        std::cout << "      move  " << name << "   (alive=" << alive << ")\n";
    }
    Tracker& operator=(const Tracker&) = default;
    Tracker& operator=(Tracker&&)      = default;

    ~Tracker() {
        --alive;
        std::cout << "      dtor  " << name << "   (alive=" << alive << ")\n";
    }
};
int Tracker::alive = 0;

// ---------------------------------------------------------------------------

static void section(const std::string& title) {
    std::cout << "\n=== " << title << " ===\n";
}

static void print(const std::string& label, const MyVector<int>& v) {
    std::cout << label << " size=" << v.size()
              << " capacity=" << v.capacity() << "  [";
    for (int x : v) std::cout << ' ' << x;
    std::cout << " ]\n";
}

int main() {
    section("1. push_back and automatic growth");
    {
        MyVector<int> v;
        for (int i = 1; i <= 10; ++i) {
            v.push_back(i * i);
            std::cout << "  push_back(" << i * i << ")"
                      << "  size=" << v.size()
                      << "  capacity=" << v.capacity() << '\n';
        }
        print("  v:", v);
        std::cout << "  v[3]=" << v[3] << "  front=" << v.front()
                  << "  back=" << v.back() << '\n';
    }

    section("2. at() performs bounds checking");
    {
        MyVector<int> v{10, 20, 30};
        try {
            std::cout << v.at(99) << '\n';
        } catch (const std::out_of_range& e) {
            std::cout << "  caught std::out_of_range: " << e.what() << '\n';
        }
    }

    section("3. copy = deep copy, move = steal the buffer");
    {
        MyVector<int> a{1, 2, 3};
        MyVector<int> b = a;          // copy constructor
        b.push_back(4);
        print("  a:", a);
        print("  b:", b);

        MyVector<int> c = std::move(a);   // move constructor
        print("  c (moved from a):", c);
        print("  a (after move)  :", a);
    }

    section("4. insert / erase / resize");
    {
        MyVector<int> v{1, 2, 3, 4, 5};
        print("  start        :", v);

        v.erase(v.begin() + 1);           // drop the element '2'
        print("  erase [1]    :", v);

        v.insert(v.begin(), 0);           // prepend 0
        print("  insert begin :", v);

        v.resize(8, 99);                  // grow, filling with 99
        print("  resize(8, 99):", v);

        v.resize(3);                      // shrink
        print("  resize(3)    :", v);
    }

    section("5. object lifetimes (no leaks, no double frees)");
    {
        std::cout << "  -- emplace_back two Trackers\n";
        MyVector<Tracker> t;
        t.emplace_back("alpha");
        t.emplace_back("beta");

        std::cout << "  -- reserve(8) forces a reallocation (elements are moved)\n";
        t.reserve(8);

        std::cout << "  -- leaving the scope\n";
    }
    std::cout << "  Trackers still alive: " << Tracker::alive << "  (expected 0)\n";
    assert(Tracker::alive == 0);

    std::cout << "\nAll demos finished.\n";
    return 0;
}
