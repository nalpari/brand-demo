package com.eland.brand.auth;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

	private static final Duration TOKEN_TTL = Duration.ofHours(1);

	private static final int MAX_USERNAME_LENGTH = 50;

	private static final int MIN_PASSWORD_LENGTH = 8;

	/** BCrypt hashes the first 72 bytes and silently drops the rest. */
	private static final int MAX_PASSWORD_BYTES = 72;

	private static final String ADMIN = "ADMIN";

	/** The key is a shared secret, so the header has to say HMAC; the default is RSA. */
	private static final JwsHeader HS256 = JwsHeader.with(MacAlgorithm.HS256).build();

	private final UserMapper mapper;

	private final PasswordEncoder passwordEncoder;

	private final JwtEncoder jwtEncoder;

	/**
	 * A hash to check a password against when the username does not exist, so that an
	 * unknown username costs the same BCrypt round as a wrong password. Without it the
	 * response time tells an attacker which usernames are real.
	 */
	private final String absentUserHash;

	AuthService(UserMapper mapper, PasswordEncoder passwordEncoder, JwtEncoder jwtEncoder) {
		this.mapper = mapper;
		this.passwordEncoder = passwordEncoder;
		this.jwtEncoder = jwtEncoder;
		this.absentUserHash = passwordEncoder.encode("no-such-user");
	}

	public AuthToken login(String username, String password) {
		requireCredentials(username, password);
		// Before the row, not after it. The row carries the revocation cutoff, and a change
		// committing between the two reads is invisible to this call either way — but the
		// order decides which way it falls. Reading the clock last dates the token after a
		// cutoff this call never saw, and `isTokenStale` then waves it through for its full
		// hour: a password change fails to strand a token minted with the old password.
		// Reading it first closes both branches. If the change lands before the row read,
		// the row carries the new hash and the password does not match — 401. If it lands
		// after, `iat` predates the new cutoff and the token is refused on first use, and
		// the caller logs in again. The cost is that `iat` is one BCrypt round earlier than
		// the issue time, which only shortens the token's own life.
		Instant clock = mapper.currentInstant().toInstant();
		User user = mapper.findByUsername(username);
		String hash = user != null ? user.getPasswordHash() : absentUserHash;
		if (!passwordEncoder.matches(password, hash) || user == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "invalid username or password");
		}
		// The database clock, not this JVM's. `password_changed_at` is stamped by Postgres and
		// isTokenStale compares the two: read from different clocks, any skew between the app
		// host and the database either strands fresh tokens or lets revoked ones live past the
		// change. One clock writes both sides.
		// Truncated because the `exp` and `iat` claims hold whole seconds, so this reports the
		// expiry the token actually carries rather than one up to a second later.
		Instant issuedAt = clock.truncatedTo(ChronoUnit.SECONDS);
		// A login never hands out a token its own account would already refuse. Truncating
		// `iat` puts it up to a second earlier than the real issue time, so a token issued
		// in the same second as the last password change — the ordinary signup-then-login
		// path, since signup stamps the column too — would come back stale. Rounding up to
		// the next whole second past the cutoff fixes that without the alternative, which is
		// to floor the cutoff as well: that reads *not stale* for a token issued earlier in
		// the same second as the change, and a stolen one then survives the change it should
		// have died to. The `iat` can land up to a second ahead of the real issue time, which
		// nothing validates and which only shortens no lifetime.
		Instant cutoff = user.getPasswordChangedAt().toInstant();
		if (issuedAt.isBefore(cutoff)) {
			issuedAt = cutoff.truncatedTo(ChronoUnit.SECONDS).plusSeconds(1);
		}
		Instant expiresAt = issuedAt.plus(TOKEN_TTL);
		JwtClaimsSet claims = JwtClaimsSet.builder()
			.subject(user.getUsername())
			.issuedAt(issuedAt)
			.expiresAt(expiresAt)
			.build();
		return new AuthToken(jwtEncoder.encode(JwtEncoderParameters.from(HS256, claims)).getTokenValue(), expiresAt);
	}


	// --- accounts ---------------------------------------------------------------------

	@Transactional
	public User signup(String username, String password) {
		String name = requireUsername(username);
		requirePassword(password);
		User user = new User();
		user.setUsername(name);
		user.setPasswordHash(passwordEncoder.encode(password));
		try {
			mapper.insert(user);
		}
		catch (DuplicateKeyException ex) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "username is already taken");
		}
		// insert's RETURNING already filled role, createdAt and passwordChangedAt.
		return withoutHash(user);
	}

	public User find(String callerUsername, String target) {
		return withoutHash(resolve(callerUsername, target));
	}

	/**
	 * The same rule as {@link #find}, keyed by username instead of id. Restricted to the
	 * caller's own name and to admins for a reason: answering "does this username exist"
	 * for anybody would be the account enumeration that {@link #login} pays a wasted BCrypt
	 * round to prevent, and signup is anonymous, so one request buys the token to ask with.
	 * A plain caller therefore gets `403` for any other name, present or not.
	 */
	public User findByUsername(String callerUsername, String username) {
		// Through the same guards as signup, so a name that could never have been stored is
		// a `400` here rather than a lookup that cannot match, and a padded one finds the
		// account it names.
		String name = requireUsername(username);
		User caller = requireCaller(callerUsername);
		if (name.equals(caller.getUsername())) {
			return withoutHash(caller);
		}
		if (!ADMIN.equals(caller.getRole())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "not your account");
		}
		User found = mapper.findByUsername(name);
		if (found == null) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "no such account");
		}
		return withoutHash(found);
	}

	/**
	 * A caller changing their own password must prove they know the current one — a stolen
	 * token would otherwise be a permanent takeover. An admin resetting somebody else's
	 * does not, because the point of a reset is that nobody knows the old one.
	 */
	@Transactional
	public void changePassword(String callerUsername, String target, String currentPassword, String newPassword) {
		User user = resolve(callerUsername, target);
		if (user.getUsername().equals(callerUsername)
				&& !passwordEncoder.matches(currentPassword == null ? "" : currentPassword, user.getPasswordHash())) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "current password does not match");
		}
		requirePassword(newPassword);
		// The row can move between resolve() loading it and this update: a concurrent delete,
		// or another password change committing in the two BCrypt rounds this method spends
		// on the row. The update carries the hash resolve() verified against, so it applies
		// only while the row still holds it — otherwise this write would overwrite the change
		// that beat it, handing the account to a caller whose proof is no longer current and
		// stranding the tokens the winning change issued. Reporting 204 for a write that
		// touched nothing tells the caller a password was set that was not; SampleService
		// checks the same counts.
		if (mapper.updatePassword(user.getId(), user.getPasswordHash(), passwordEncoder.encode(newPassword)) != 1) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "the account changed while the password was being set");
		}
	}

	@Transactional
	public void delete(String callerUsername, String target) {
		if (mapper.deleteById(resolve(callerUsername, target).getId()) != 1) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "no such account");
		}
	}

	/**
	 * Whether a token signed for this account should now be refused: the account is gone,
	 * or its password changed after the token was issued. Both timestamps are compared at
	 * whole-second precision because that is all the `iat` claim carries, which leaves a
	 * sub-second window where a token issued in the same second as a change still passes.
	 */
	public boolean isTokenStale(String username, Instant issuedAt) {
		User user = username == null ? null : mapper.findByUsername(username);
		if (user == null) {
			return true;
		}
		// The cutoff keeps its full precision. `issuedAt` is already whole seconds, so
		// flooring the cutoff as well would answer *not stale* for a token issued earlier in
		// the same second as the change — the fail-open half of an ambiguity that cannot be
		// removed at this resolution. The cost of the closed half is that a token issued
		// later in that same second is also refused, and its owner logs in again.
		return issuedAt == null || issuedAt.isBefore(user.getPasswordChangedAt().toInstant());
	}

	/**
	 * The one authorization rule in this service: a caller reaches their own account, and
	 * an admin reaches anyone's. A plain caller naming another id is refused without the
	 * row being looked up, so the response cannot say whether that id exists.
	 */
	private User resolve(String callerUsername, String target) {
		User caller = requireCaller(callerUsername);
		if ("me".equals(target)) {
			return caller;
		}
		long id;
		try {
			id = Long.parseLong(target);
		}
		catch (NumberFormatException ex) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "id must be a number or 'me'");
		}
		if (id == caller.getId()) {
			return caller;
		}
		if (!ADMIN.equals(caller.getRole())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "not your account");
		}
		User target_ = mapper.findById(id);
		if (target_ == null) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "no such account");
		}
		return target_;
	}

	/** The token was valid, so the row should be there; it is not if the account just went. */
	private User requireCaller(String callerUsername) {
		User caller = mapper.findByUsername(callerUsername);
		if (caller == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "no such account");
		}
		return caller;
	}

	/**
	 * Belt and braces over {@code @JsonIgnore}: nothing that leaves here carries the hash.
	 * <p>
	 * Returns a copy rather than stripping the argument. The argument is the instance MyBatis
	 * holds in its local cache for the rest of the transaction, so nulling it would disarm
	 * any password check that re-reads the same row later in that transaction — the check
	 * would compare against {@code null} and refuse the correct password.
	 */
	private User withoutHash(User user) {
		User copy = new User();
		copy.setId(user.getId());
		copy.setUsername(user.getUsername());
		copy.setRole(user.getRole());
		copy.setCreatedAt(user.getCreatedAt());
		copy.setPasswordChangedAt(user.getPasswordChangedAt());
		return copy;
	}

	/**
	 * Validates and returns the name to use. The same guards as
	 * {@code SampleService.requireName}, and for the same reasons: `isBlank` passes a name
	 * made only of zero-width or other invisible code points, which would put a row — and a
	 * JWT `sub` — that nothing can read on screen; and Postgres refuses a NUL byte in a text
	 * parameter, so an unguarded one reaches an anonymous endpoint as a `500`.
	 * <p>
	 * Surrounding whitespace is trimmed rather than rejected. `users_username_key` is a
	 * plain btree on `text`, so `" alice"` and `"alice"` are two accounts that render
	 * identically everywhere a name is shown. Trimming makes the second one a `409`.
	 */
	private String requireUsername(String username) {
		if (username != null && username.codePointCount(0, username.length()) > MAX_USERNAME_LENGTH) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
					"username must be at most " + MAX_USERNAME_LENGTH + " characters");
		}
		if (username == null || username.replaceAll("[\\p{Z}\\p{C}]", "").isEmpty()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "username is required");
		}
		if (username.indexOf('\0') >= 0) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "username must not contain NUL");
		}
		return username.trim();
	}

	private void requirePassword(String password) {
		if (password == null || password.length() < MIN_PASSWORD_LENGTH) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
					"password must be at least " + MIN_PASSWORD_LENGTH + " characters");
		}
		if (password.getBytes(StandardCharsets.UTF_8).length > MAX_PASSWORD_BYTES) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
					"password must be at most " + MAX_PASSWORD_BYTES + " bytes");
		}
	}

	private void requireCredentials(String username, String password) {
		if (username == null || username.isBlank() || password == null || password.isBlank()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "username and password are required");
		}
	}

}
