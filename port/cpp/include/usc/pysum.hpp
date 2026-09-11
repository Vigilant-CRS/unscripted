// Python's `sum()` over floats, which since CPython 3.12 is NOT a loop of
// additions.
//
// FOUND BY MEASUREMENT, not by reading the source. The ported identity engine
// disagreed with Python by one bit from the second round onward, and every
// compiler flag was ruled out first -- -O0 through -O3, -march=native,
// -ffp-contract=off -- because the obvious suspect was FMA contraction. It was
// not. The C++ naive sum of a softmax gave 0.99999999999999989 where Python's
// `sum()` gave exactly 1.0, and dividing by one or the other is the difference.
//
// CPython 3.12 gave `sum()` a fast path for floats that uses Neumaier
// (Kahan-Babuska) compensated summation. The core of this runtime calls `sum()`
// over floats in nineteen places, so a port that adds in a loop is wrong in all
// of them -- quietly, by a bit at a time.
//
// TWO CONSEQUENCES, and the second is about the Python side rather than this
// one.
//
// A port must compensate. That is what this file is for.
//
// And the reference implementation's own numbers depend on the interpreter
// version. On Python 3.10 and 3.11 `sum()` adds naively, so the committed
// conformance fixtures -- generated on 3.14 -- do not reproduce bit-exactly
// there. Measured rather than feared: 12 fields move, the worst by 0.9 ULP, no
// discrete outcome changes, and `--port` tolerance absorbs it entirely. It is
// recorded in `port/README.md` because somebody running the SDK on 3.10 and
// seeing a fixture fail deserves to find the answer rather than hunt it.
#pragma once

#include <cmath>
#include <vector>

namespace usc {

/// Neumaier compensated summation, matching CPython's float fast path.
///
/// Starts at 0.0 with zero compensation, because `sum(xs)` starts at int 0 and
/// converts on the first float.
class PySum {
public:
    void add(double value) {
        double t = total_ + value;
        // Which operand is larger decides where the lost low-order bits are.
        if (std::fabs(total_) >= std::fabs(value)) compensation_ += (total_ - t) + value;
        else                                       compensation_ += (value - t) + total_;
        total_ = t;
        ++count_;
    }

    double value() const { return total_ + compensation_; }

    /// Whether anything was added at all. `sum()` of an empty sequence returns
    /// the integer 0, not 0.0 -- and that difference is visible in exported
    /// state as `0` rather than `0.0`.
    bool empty() const { return count_ == 0; }

private:
    double total_ = 0.0;
    double compensation_ = 0.0;
    long long count_ = 0;
};

inline double py_sum(const std::vector<double>& values) {
    PySum accumulator;
    for (double value : values) accumulator.add(value);
    return accumulator.value();
}

}  // namespace usc
