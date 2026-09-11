package com.eland.brand.auth;

import java.time.Instant;

/** What {@code POST /api/auth/login} returns: the bearer token and when it stops working. */
public record AuthToken(String token, Instant expiresAt) {
}
