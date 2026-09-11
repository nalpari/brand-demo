package com.eland.brand.auth;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;

public class User {

	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private Long id;

	private String username;

	/** Inbound only: the plaintext a login request carries. Never read from the database. */
	@JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
	private String password;

	/** The stored BCrypt hash. Kept out of JSON in both directions. */
	@JsonIgnore
	private String passwordHash;

	/**
	 * `USER` or `ADMIN`. Read-only in JSON on purpose: signup is anonymous, so a request
	 * that could set this would be an anonymous route to an admin account. Promotion is a
	 * `psql` update — see okf/tables/users.md.
	 */
	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private String role;

	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private OffsetDateTime createdAt;

	/** Tokens issued before this instant are refused. Written on every password change. */
	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private OffsetDateTime passwordChangedAt;

	public Long getId() {
		return id;
	}

	public void setId(Long id) {
		this.id = id;
	}

	public String getUsername() {
		return username;
	}

	public void setUsername(String username) {
		this.username = username;
	}

	public String getPassword() {
		return password;
	}

	public void setPassword(String password) {
		this.password = password;
	}

	public String getPasswordHash() {
		return passwordHash;
	}

	public void setPasswordHash(String passwordHash) {
		this.passwordHash = passwordHash;
	}

	public String getRole() {
		return role;
	}

	public void setRole(String role) {
		this.role = role;
	}

	public OffsetDateTime getPasswordChangedAt() {
		return passwordChangedAt;
	}

	public void setPasswordChangedAt(OffsetDateTime passwordChangedAt) {
		this.passwordChangedAt = passwordChangedAt;
	}

	public OffsetDateTime getCreatedAt() {
		return createdAt;
	}

	public void setCreatedAt(OffsetDateTime createdAt) {
		this.createdAt = createdAt;
	}

}
