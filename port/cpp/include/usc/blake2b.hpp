// BLAKE2b, RFC 7693, header-only and dependency-free.
//
// Vendored rather than linked. A console build should not need OpenSSL, and the
// Python side reaches this through `hashlib`, which is part of its standard
// library -- so the C++ side has to carry its own or the two are not comparable
// on a machine where one of them is missing.
//
// This is the reference construction with nothing added. It is here because
// every seeded draw in the runtime derives from
// blake2b(global_seed|agent|event|time|module|salt), and a port that gets one
// bit of that wrong diverges on the first coin flip and looks correct until it
// does.
#pragma once

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace usc {

class Blake2b {
public:
    explicit Blake2b(std::size_t digest_size = 64) : digest_size_(digest_size) {
        static const std::uint64_t iv[8] = {
            0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL,
            0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
            0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL,
            0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL};
        for (int i = 0; i < 8; ++i) h_[i] = iv[i];
        // Parameter block: digest length, no key, fanout 1, depth 1.
        h_[0] ^= 0x01010000ULL ^ static_cast<std::uint64_t>(digest_size);
    }

    void update(const std::uint8_t* data, std::size_t len) {
        for (std::size_t i = 0; i < len; ++i) {
            if (buffer_len_ == 128) {
                counter_ += 128;
                compress(false);
                buffer_len_ = 0;
            }
            buffer_[buffer_len_++] = data[i];
        }
    }

    void update(const std::string& text) {
        update(reinterpret_cast<const std::uint8_t*>(text.data()), text.size());
    }

    std::vector<std::uint8_t> digest() {
        counter_ += buffer_len_;
        while (buffer_len_ < 128) buffer_[buffer_len_++] = 0;
        compress(true);
        std::vector<std::uint8_t> out(digest_size_);
        for (std::size_t i = 0; i < digest_size_; ++i)
            out[i] = static_cast<std::uint8_t>((h_[i >> 3] >> (8 * (i & 7))) & 0xFF);
        return out;
    }

private:
    static std::uint64_t rotr(std::uint64_t x, unsigned n) {
        return (x >> n) | (x << (64 - n));
    }

    void compress(bool last) {
        static const std::uint8_t sigma[12][16] = {
            {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
            {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3},
            {11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4},
            {7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8},
            {9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13},
            {2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9},
            {12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11},
            {13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10},
            {6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5},
            {10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0},
            {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15},
            {14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3}};
        static const std::uint64_t iv[8] = {
            0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL,
            0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
            0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL,
            0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL};

        std::uint64_t m[16];
        for (int i = 0; i < 16; ++i) {
            std::uint64_t word = 0;
            for (int b = 7; b >= 0; --b)
                word = (word << 8) | buffer_[i * 8 + b];
            m[i] = word;
        }
        std::uint64_t v[16];
        for (int i = 0; i < 8; ++i) v[i] = h_[i];
        for (int i = 0; i < 8; ++i) v[i + 8] = iv[i];
        v[12] ^= counter_;
        v[13] ^= 0;                       // high half of the counter
        if (last) v[14] = ~v[14];

        auto mix = [&](int a, int b, int c, int d, std::uint64_t x, std::uint64_t y) {
            v[a] = v[a] + v[b] + x;  v[d] = rotr(v[d] ^ v[a], 32);
            v[c] = v[c] + v[d];      v[b] = rotr(v[b] ^ v[c], 24);
            v[a] = v[a] + v[b] + y;  v[d] = rotr(v[d] ^ v[a], 16);
            v[c] = v[c] + v[d];      v[b] = rotr(v[b] ^ v[c], 63);
        };
        for (int round = 0; round < 12; ++round) {
            const std::uint8_t* s = sigma[round];
            mix(0, 4,  8, 12, m[s[0]],  m[s[1]]);
            mix(1, 5,  9, 13, m[s[2]],  m[s[3]]);
            mix(2, 6, 10, 14, m[s[4]],  m[s[5]]);
            mix(3, 7, 11, 15, m[s[6]],  m[s[7]]);
            mix(0, 5, 10, 15, m[s[8]],  m[s[9]]);
            mix(1, 6, 11, 12, m[s[10]], m[s[11]]);
            mix(2, 7,  8, 13, m[s[12]], m[s[13]]);
            mix(3, 4,  9, 14, m[s[14]], m[s[15]]);
        }
        for (int i = 0; i < 8; ++i) h_[i] ^= v[i] ^ v[i + 8];
    }

    std::uint64_t h_[8]{};
    std::uint8_t buffer_[128]{};
    std::size_t buffer_len_ = 0;
    std::uint64_t counter_ = 0;
    std::size_t digest_size_;
};

}  // namespace usc
