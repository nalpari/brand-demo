package com.eland.brand.auth;

import java.time.OffsetDateTime;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface UserMapper {

	/** The database's clock, which is the only clock that writes `password_changed_at`. */
	OffsetDateTime currentInstant();

	User findByUsername(String username);

	User findById(long id);

	int insert(User user);

	/**
	 * Writes the new hash only while the row still carries {@code expectedHash} — the hash
	 * {@code changePassword} checked the current password against. Returns 0 when it does
	 * not, which is a concurrent change this write must not overwrite.
	 */
	int updatePassword(@Param("id") long id, @Param("expectedHash") String expectedHash,
			@Param("passwordHash") String passwordHash);

	int deleteById(long id);

}
