// SHA-256 (FIPS 180-4), vendored.
//
// The port already carries BLAKE2b for `derive_seed`, and one hash is not the
// other: the state envelope's world fingerprint is a SHA-256, and a save written
// by the Python build has to be recognisable to the C++ one and the other way
// round. So the second hash is here for the same reason as the first -- a
// dependency-free core cannot link OpenSSL, and a fingerprint that differed
// between implementations would reject every cross-build save.
//
// About a hundred lines, transcribed from the standard and checked against the
// published test vectors in the probe.
#pragma once

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace usc {

namespace detail_ {

inline constexpr std::uint32_t SHA256_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u,
    0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u,
    0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
    0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au,
    0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

inline std::uint32_t rotr32(std::uint32_t value, int bits) {
    return (value >> bits) | (value << (32 - bits));
}

}  // namespace detail_

/// The digest of `message`, as 32 raw bytes.
inline std::vector<std::uint8_t> sha256(const std::string& message) {
    std::uint32_t h[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                          0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};

    std::vector<std::uint8_t> data(message.begin(), message.end());
    const std::uint64_t bits = static_cast<std::uint64_t>(data.size()) * 8;
    data.push_back(0x80);
    while (data.size() % 64 != 56) data.push_back(0x00);
    for (int i = 7; i >= 0; --i)
        data.push_back(static_cast<std::uint8_t>((bits >> (i * 8)) & 0xFF));

    for (std::size_t block = 0; block < data.size(); block += 64) {
        std::uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (static_cast<std::uint32_t>(data[block + i * 4]) << 24)
                 | (static_cast<std::uint32_t>(data[block + i * 4 + 1]) << 16)
                 | (static_cast<std::uint32_t>(data[block + i * 4 + 2]) << 8)
                 | (static_cast<std::uint32_t>(data[block + i * 4 + 3]));
        for (int i = 16; i < 64; ++i) {
            std::uint32_t s0 = detail_::rotr32(w[i - 15], 7)
                             ^ detail_::rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
            std::uint32_t s1 = detail_::rotr32(w[i - 2], 17)
                             ^ detail_::rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }

        std::uint32_t a = h[0], b = h[1], c = h[2], d = h[3];
        std::uint32_t e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i) {
            std::uint32_t S1 = detail_::rotr32(e, 6) ^ detail_::rotr32(e, 11)
                             ^ detail_::rotr32(e, 25);
            std::uint32_t ch = (e & f) ^ ((~e) & g);
            std::uint32_t temp1 = hh + S1 + ch + detail_::SHA256_K[i] + w[i];
            std::uint32_t S0 = detail_::rotr32(a, 2) ^ detail_::rotr32(a, 13)
                             ^ detail_::rotr32(a, 22);
            std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            std::uint32_t temp2 = S0 + maj;
            hh = g; g = f; f = e; e = d + temp1;
            d = c; c = b; b = a; a = temp1 + temp2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d;
        h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }

    std::vector<std::uint8_t> digest(32);
    for (int i = 0; i < 8; ++i) {
        digest[i * 4]     = static_cast<std::uint8_t>((h[i] >> 24) & 0xFF);
        digest[i * 4 + 1] = static_cast<std::uint8_t>((h[i] >> 16) & 0xFF);
        digest[i * 4 + 2] = static_cast<std::uint8_t>((h[i] >> 8) & 0xFF);
        digest[i * 4 + 3] = static_cast<std::uint8_t>(h[i] & 0xFF);
    }
    return digest;
}

/// `hashlib.sha256(text.encode("utf-8")).hexdigest()`.
inline std::string sha256_hex(const std::string& message) {
    static const char* digits = "0123456789abcdef";
    std::string out;
    for (std::uint8_t byte : sha256(message)) {
        out += digits[byte >> 4];
        out += digits[byte & 0x0F];
    }
    return out;
}

}  // namespace usc
