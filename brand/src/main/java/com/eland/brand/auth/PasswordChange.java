package com.eland.brand.auth;

/** Body of {@code PUT /api/users/{id}}. `currentPassword` is unused when an admin resets someone else's. */
public record PasswordChange(String currentPassword, String newPassword) {
}
