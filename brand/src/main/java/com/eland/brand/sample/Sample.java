package com.eland.brand.sample;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;

public class Sample {

	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private Long id;

	private String name;

	@JsonProperty(access = JsonProperty.Access.READ_ONLY)
	private OffsetDateTime createdAt;

	public Long getId() {
		return id;
	}

	public void setId(Long id) {
		this.id = id;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public OffsetDateTime getCreatedAt() {
		return createdAt;
	}

	public void setCreatedAt(OffsetDateTime createdAt) {
		this.createdAt = createdAt;
	}

}
