// A map that remembers the order things were put into it.
//
// THE SINGLE MOST IMPORTANT TYPE IN THIS PORT, and the least interesting to
// read. Python dictionaries have preserved insertion order since 3.7, and this
// runtime leans on that in more places than are obvious:
//
//   - `Proposition.slots` -- iterated to build `core_key()`, which is the
//     identity a belief is stored under. A different order is a different key,
//     so two implementations would disagree about whether they hold the same
//     belief at all.
//   - `beliefs` -- iterated in the contradiction scan, and the order decides
//     which contradiction gets reported first.
//   - `origin_counts` -- `primary_origin` is `next(iter(...))`, the *first*
//     origin heard. That is what makes a rumour relayed through five mouths
//     worth one witness rather than five, and with an unordered container it
//     becomes whichever one hashed lowest.
//
// `std::unordered_map` gets all three wrong, quietly, in a way that reproduces
// on one machine and not another. `std::map` gets them wrong differently, by
// sorting. Hence this: a vector for order, a hash index for lookup.
//
// It is the bug the conformance fixtures exist to catch and the reason the
// port order puts perception and diffusion behind belief -- those modules walk
// collections while drawing seeded numbers, so an order difference there does
// not shift a number, it changes who overhears what.
#pragma once

#include <cstddef>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace usc {

template <typename Value>
class OrderedMap {
public:
    using Entry = std::pair<std::string, Value>;
    using const_iterator = typename std::vector<Entry>::const_iterator;
    using iterator = typename std::vector<Entry>::iterator;

    bool contains(const std::string& key) const {
        return index_.find(key) != index_.end();
    }

    /// Insert at the back, or overwrite in place. Overwriting must NOT move the
    /// entry to the end: Python's `d[k] = v` leaves an existing key where it
    /// was, and `origin_counts[key] += 1` relies on that every time a repeat is
    /// heard.
    Value& operator[](const std::string& key) {
        auto found = index_.find(key);
        if (found != index_.end()) return entries_[found->second].second;
        index_.emplace(key, entries_.size());
        entries_.emplace_back(key, Value{});
        return entries_.back().second;
    }

    const Value* find(const std::string& key) const {
        auto found = index_.find(key);
        return found == index_.end() ? nullptr : &entries_[found->second].second;
    }

    Value* find(const std::string& key) {
        auto found = index_.find(key);
        return found == index_.end() ? nullptr : &entries_[found->second].second;
    }

    /// `d.get(key, fallback)`.
    Value get(const std::string& key, const Value& fallback = Value{}) const {
        const Value* found = find(key);
        return found ? *found : fallback;
    }

    const Entry* first() const { return entries_.empty() ? nullptr : &entries_.front(); }

    std::size_t size() const { return entries_.size(); }
    bool empty() const { return entries_.empty(); }
    const_iterator begin() const { return entries_.begin(); }
    const_iterator end() const { return entries_.end(); }
    iterator begin() { return entries_.begin(); }
    iterator end() { return entries_.end(); }

    /// `d.pop(key, None)` -- remove a key and keep everything else in the order
    /// it was inserted. Returns whether anything was there.
    ///
    /// Linear in the size of the map, because every later entry's index has to
    /// move down one. That is the price of holding the order in a vector, and it
    /// is paid only where Python pays it too: removing from a dict is rare in
    /// this runtime and never happens inside a loop over the same dict.
    bool erase(const std::string& key) {
        auto found = index_.find(key);
        if (found == index_.end()) return false;
        std::size_t at = found->second;
        entries_.erase(entries_.begin() + static_cast<long>(at));
        index_.erase(found);
        for (auto& entry : index_) if (entry.second > at) --entry.second;
        return true;
    }

    void clear() { entries_.clear(); index_.clear(); }

private:
    std::vector<Entry> entries_;
    std::unordered_map<std::string, std::size_t> index_;
};

}  // namespace usc
