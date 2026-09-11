package com.eland.brand.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;
import java.time.temporal.ChronoUnit;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@SpringBootTest
@Transactional
class AuthServiceTest {

	@Autowired
	private AuthService service;

	@Autowired
	private JwtDecoder decoder;

	@Autowired
	private PasswordEncoder passwordEncoder;

	@Autowired
	private JdbcTemplate jdbc;

	@Autowired
	private UserMapper mapper;

	@Test
	void loginIssuesATokenTheDecoderAccepts() {
		account("alice", "correct-horse");

		AuthToken issued = service.login("alice", "correct-horse");

		Jwt jwt = decoder.decode(issued.token());
		assertThat(jwt.getSubject()).isEqualTo("alice");
		assertThat(jwt.getExpiresAt()).isEqualTo(issued.expiresAt());
		assertThat(issued.expiresAt()).isCloseTo(Instant.now().plus(1, ChronoUnit.HOURS),
				within(1, ChronoUnit.MINUTES));
	}

	@Test
	void loginRejectsAWrongPassword() {
		account("bob", "correct-horse");

		assertThatThrownBy(() -> service.login("bob", "battery-staple"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void loginRejectsAnUnknownUsernameWithTheSameStatusAsAWrongPassword() {
		assertThatThrownBy(() -> service.login("nobody-here", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void loginRejectsBlankCredentials() {
		assertThatThrownBy(() -> service.login("  ", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}


	// --- accounts: signup, read, change password, delete -------------------------------

	@Test
	void signupCreatesAUserThatCanImmediatelyLogIn() {
		User created = service.signup("newcomer", "correct-horse");

		assertThat(created.getId()).isNotNull();
		assertThat(created.getRole()).isEqualTo("USER");
		assertThat(created.getPasswordHash()).isNull();
		assertThat(service.login("newcomer", "correct-horse").token()).isNotBlank();
	}

	@Test
	void signupRejectsADuplicateUsernameWithConflict() {
		service.signup("taken", "correct-horse");

		assertThatThrownBy(() -> service.signup("taken", "another-one")).isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.CONFLICT);
	}

	@Test
	void signupRejectsAPasswordShorterThanEightCharactersOrLongerThanBcryptReads() {
		assertThatThrownBy(() -> service.signup("shorty", "1234567")).isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
		assertThatThrownBy(() -> service.signup("wordy", "x".repeat(73))).isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void findResolvesMeToTheCallerAndNeverCarriesTheHash() {
		User self = service.signup("reader", "correct-horse");

		User found = service.find("reader", "me");

		assertThat(found.getId()).isEqualTo(self.getId());
		assertThat(found.getUsername()).isEqualTo("reader");
		assertThat(found.getPasswordHash()).isNull();
	}

	@Test
	void aPlainUserCannotReachAnotherAccount() {
		User other = service.signup("victim", "correct-horse");
		service.signup("nosy", "correct-horse");

		assertThatThrownBy(() -> service.find("nosy", String.valueOf(other.getId())))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);
	}

	@Test
	void anAdminCanReachAnotherAccount() {
		User other = service.signup("watched", "correct-horse");
		admin("overseer");

		assertThat(service.find("overseer", String.valueOf(other.getId())).getUsername()).isEqualTo("watched");
	}

	@Test
	void changingOwnPasswordRequiresTheCurrentOne() {
		service.signup("careful", "correct-horse");

		assertThatThrownBy(() -> service.changePassword("careful", "me", "wrong-one", "battery-staple"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.UNAUTHORIZED);

		service.changePassword("careful", "me", "correct-horse", "battery-staple");
		assertThat(service.login("careful", "battery-staple").token()).isNotBlank();
	}

	@Test
	void anAdminResetsAPasswordWithoutKnowingTheOldOne() {
		User target = service.signup("forgetful", "correct-horse");
		admin("helpdesk");

		service.changePassword("helpdesk", String.valueOf(target.getId()), null, "battery-staple");

		assertThat(service.login("forgetful", "battery-staple").token()).isNotBlank();
	}

	@Test
	void readingAnAccountDoesNotDisarmItsOwnPasswordCheck() {
		service.signup("reader", "correct-horse");

		// find hands back the caller's row with the hash stripped. That strip must not land
		// on the instance MyBatis keeps in its local cache for the rest of the transaction:
		// changePassword re-reads the same row to check the current password, and against a
		// nulled hash that check fails with 401 no matter what the caller typed.
		service.find("reader", "me");

		service.changePassword("reader", "me", "correct-horse", "battery-staple");

		assertThat(service.login("reader", "battery-staple").token()).isNotBlank();
	}

	@Test
	void aChangedPasswordStrandsTokensIssuedBeforeIt() {
		service.signup("rotator", "correct-horse");
		Instant cutoffBefore = cutoffOf("rotator");

		service.changePassword("rotator", "me", "correct-horse", "battery-staple");

		// The column has to actually move, and it cannot under now(): this class is
		// @Transactional, so now() is frozen at the test transaction's start — the same
		// value signup's column default already wrote. Asserting against a fixed instant
		// instead of against this delta is what let the old version of this test pass
		// with the whole `password_changed_at = ...` clause deleted from updatePassword.
		Instant cutoff = cutoffOf("rotator");
		assertThat(cutoff).isAfter(cutoffBefore);

		// Whole seconds, because that is the iat resolution; a token from the second the
		// change landed in is deliberately not stranded.
		assertThat(service.isTokenStale("rotator", cutoff.truncatedTo(ChronoUnit.SECONDS).minusSeconds(1))).isTrue();
		assertThat(service.isTokenStale("rotator", cutoff.plusSeconds(1))).isFalse();
	}

	/**
	 * The other side of {@link #aTokenFromTheSameSecondAsTheChangeIsStale}: closing that
	 * window must not strand the caller who just changed their own password and is logging
	 * back in within the same second. The decoder carries the staleness validator, so a
	 * token it accepts is one the API accepts.
	 */
	@Test
	void aLoginRightAfterAPasswordChangeIssuesAUsableToken() {
		service.signup("hurried", "correct-horse");
		service.changePassword("hurried", "me", "correct-horse", "battery-staple");

		String token = service.login("hurried", "battery-staple").token();

		assertThat(decoder.decode(token).getSubject()).isEqualTo("hurried");
	}

	/**
	 * The cutoff must not be floored to the second. A token's `iat` already carries only
	 * whole seconds, so flooring the cutoff too collapses "issued at 10:00:00.100" and
	 * "changed at 10:00:00.900" onto the same value and the comparison answers *not stale* —
	 * a stolen token issued in the same second as the change it should have died to keeps
	 * working for its full hour. Comparing whole-second `iat` against the real cutoff biases
	 * the unavoidable sub-second ambiguity the other way: closed.
	 */
	@Test
	void aTokenFromTheSameSecondAsTheChangeIsStale() {
		service.signup("same-second", "correct-horse");
		Instant cutoff = Instant.parse("2026-01-01T10:00:00.900Z");
		jdbc.update("update users set password_changed_at = ? where username = ?", Timestamp.from(cutoff),
				"same-second");

		// What a login at 10:00:00.100 would have put in the token.
		assertThat(service.isTokenStale("same-second", Instant.parse("2026-01-01T10:00:00Z"))).isTrue();
		// And the second after the change is still accepted, so the window is one second wide.
		assertThat(service.isTokenStale("same-second", Instant.parse("2026-01-01T10:00:01Z"))).isFalse();
	}

	@Test
	void aDeletedAccountStrandsEveryTokenItEverHad() {
		service.signup("leaving", "correct-horse");

		service.delete("leaving", "me");

		assertThat(service.isTokenStale("leaving", Instant.now())).isTrue();
		assertThatThrownBy(() -> service.login("leaving", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class);
	}

	@Test
	void aPlainUserCannotDeleteAnotherAccount() {
		User other = service.signup("target", "correct-horse");
		service.signup("attacker", "correct-horse");

		assertThatThrownBy(() -> service.delete("attacker", String.valueOf(other.getId())))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);
	}

	@Test
	void anAdminLooksAnAccountUpByUsername() {
		service.signup("looked-up", "correct-horse");
		admin("finder");

		User found = service.findByUsername("finder", "looked-up");

		assertThat(found.getUsername()).isEqualTo("looked-up");
		assertThat(found.getPasswordHash()).isNull();
	}

	@Test
	void aPlainUserLooksUpOnlyTheirOwnUsername() {
		service.signup("self-lookup", "correct-horse");
		service.signup("someone-else", "correct-horse");

		assertThat(service.findByUsername("self-lookup", "self-lookup").getUsername()).isEqualTo("self-lookup");

		assertThatThrownBy(() -> service.findByUsername("self-lookup", "someone-else"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);
	}

	@Test
	void aMissingUsernameIsForbiddenToAUserAndNotFoundToAnAdmin() {
		service.signup("prober", "correct-horse");
		admin("auditor");

		// A plain caller gets the same 403 whether or not the name exists, so the endpoint
		// cannot be used to find out which usernames are real.
		assertThatThrownBy(() -> service.findByUsername("prober", "ghost-account"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);

		assertThatThrownBy(() -> service.findByUsername("auditor", "ghost-account"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.NOT_FOUND);
	}

	@Test
	void aBlankUsernameIsRejectedBeforeAnyLookup() {
		service.signup("asker", "correct-horse");

		assertThatThrownBy(() -> service.findByUsername("asker", "  "))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void signupRejectsABlankUsername() {
		assertThatThrownBy(() -> service.signup("  ", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void signupRejectsAUsernameOverFiftyCharacters() {
		// username is an unbounded text column, so this guard is the only thing standing
		// between an anonymous caller and an arbitrarily long row.
		assertThat(service.signup("x".repeat(50), "correct-horse").getId()).isNotNull();

		assertThatThrownBy(() -> service.signup("x".repeat(51), "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void anIdThatIsNeitherANumberNorMeIsRejected() {
		service.signup("wanderer", "correct-horse");

		assertThatThrownBy(() -> service.find("wanderer", "you"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void anAdminNamingAMissingIdGetsNotFound() {
		admin("registrar");

		assertThatThrownBy(() -> service.find("registrar", "2147483647"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.NOT_FOUND);
	}

	/**
	 * Read straight from the column, with no mapper or local cache in between: this is the
	 * assertion that {@code updatePassword} moved {@code password_changed_at}, so it should
	 * not be able to pass on anything MyBatis chose to hand back.
	 */
	@Test
	void signupRejectsAUsernameThatIsOnlyInvisibleCharacters() {
		// isBlank() lets these through: the row would exist, and the JWT `sub` naming it
		// would be unreadable in a log or a UI. SampleService.requireName rejects the same
		// class of input for the same reason.
		assertThatThrownBy(() -> service.signup("\u200b\u200b", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void signupRejectsANulInTheUsername() {
		// Postgres refuses a NUL byte in a text parameter, so without this guard an
		// anonymous caller turns the DataAccessException into a 500.
		assertThatThrownBy(() -> service.signup("a\u0000b", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void signupTrimsTheUsernameSoSurroundingSpaceCannotForkAnAccount() {
		service.signup("alice", "correct-horse");

		// Stored untrimmed, " alice" is a second account that renders identically wherever
		// the name is shown, and the unique index does not see them as the same.
		assertThatThrownBy(() -> service.signup("  alice  ", "correct-horse"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.CONFLICT);
	}

	@Test
	void aWriteThatTouchesNoRowIsNotReportedAsSuccess() {
		admin("registrar2");
		User victim = service.signup("vanishing", "correct-horse");
		// The row goes while an admin is holding it — the concurrent case, without the race.
		jdbc.update("delete from users where id = ?", victim.getId());

		assertThatThrownBy(() -> service.changePassword("registrar2", String.valueOf(victim.getId()), null, "battery-staple"))
			.isInstanceOf(ResponseStatusException.class);
	}

	/**
	 * The hash {@code changePassword} checked {@code currentPassword} against has to still be
	 * the row's hash when the update lands. It is two statements with two BCrypt rounds
	 * between them, so another change can commit in the gap — and a bare {@code where id}
	 * update then overwrites it, handing the account to whoever proved a password that is no
	 * longer current and stranding the tokens the real change just issued.
	 * <p>
	 * No threads here: MyBatis holds the row it read for the rest of the transaction, which
	 * is the same stale read the race produces. Warming that cache and then moving the row
	 * underneath it reproduces the losing interleaving deterministically.
	 */
	@Test
	void aPasswordChangeThatVerifiedAHashTheRowNoLongerHasIsRefused() {
		service.signup("raced", "correct-horse");
		// Puts the row in the session cache, so changePassword's read below returns this
		// instance rather than the row as the next line leaves it.
		service.find("raced", "me");
		jdbc.update("update users set password_hash = ? where username = ?",
				passwordEncoder.encode("battery-staple"), "raced");

		assertThatThrownBy(() -> service.changePassword("raced", "me", "correct-horse", "hunter2-hunter2"))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.CONFLICT);

		// The concurrent change stands; the losing write left nothing behind.
		assertThat(passwordEncoder.matches("battery-staple",
				jdbc.queryForObject("select password_hash from users where username = ?", String.class, "raced")))
			.isTrue();
	}

	/**
	 * {@code withoutHash} copies field by field, so a field added to {@link User} and to the
	 * mapper but forgotten there would vanish from every API response with nothing failing.
	 * Comparing the serialized shape against the row the mapper actually returns is what
	 * notices: the two key sets have to match, minus the hash that is never serialized.
	 */
	@Test
	void whatFindReturnsCarriesEveryFieldTheRowHas() throws Exception {
		User stored = mapper.findByUsername(service.signup("shape", "correct-horse").getUsername());

		User returned = service.find("shape", "me");

		JsonMapper json = JsonMapper.builder().build();
		assertThat(json.readValue(json.writeValueAsString(returned), Map.class))
			.containsExactlyInAnyOrderEntriesOf(json.readValue(json.writeValueAsString(stored), Map.class));
	}

	private Instant cutoffOf(String username) {
		return jdbc
			.queryForObject("select password_changed_at from users where username = ?", java.sql.Timestamp.class,
					username)
			.toInstant();
	}

	private void admin(String username) {
		service.signup(username, "correct-horse");
		jdbc.update("update users set role = 'ADMIN' where username = ?", username);
	}

	private void account(String username, String password) {
		jdbc.update("insert into users (username, password_hash) values (?, ?)", username,
				passwordEncoder.encode(password));
	}

}
