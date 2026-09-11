package com.eland.brand;

import static org.assertj.core.api.Assertions.assertThat;

import com.eland.brand.auth.AuthService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.assertj.MockMvcTester;
import org.springframework.transaction.annotation.Transactional;

/**
 * The one place the filter chain's path rules are checked. It uses MockMvc rather than a
 * service call because that is the only way to reach them — the rules live in the chain,
 * not in a bean a service test can autowire. CLAUDE.md's service-layer-only testing policy
 * names this as its documented exception.
 */
@SpringBootTest(properties = "cors.allowed-origins=" + SecurityConfigTest.ALLOWED_ORIGIN)
@AutoConfigureMockMvc
@Transactional
class SecurityConfigTest {

	/** The one origin this context lets in; every other one has to be refused. */
	static final String ALLOWED_ORIGIN = "https://outside.example.com";

	@Autowired
	private MockMvcTester mvc;

	@Autowired
	private AuthService authService;

	@Autowired
	private PasswordEncoder passwordEncoder;

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	void apiRejectsACallerWithNoToken() {
		assertThat(mvc.get().uri("/api/samples")).hasStatus(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void apiRejectsAGarbageToken() {
		assertThat(mvc.get().uri("/api/samples").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
			.hasStatus(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void apiAcceptsATokenFromLogin() {
		jdbc.update("insert into users (username, password_hash) values (?, ?)", "chain-test",
				passwordEncoder.encode("correct-horse"));
		String token = authService.login("chain-test", "correct-horse").token();

		assertThat(mvc.get().uri("/api/samples").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
			.hasStatus(HttpStatus.OK);
	}

	@Test
	void loginItselfStaysAnonymous() {
		authService.signup("anon-login", "correct-horse");

		// Asserted on a *successful* login on purpose. A wrong-credentials 401 would prove
		// nothing: the filter chain returns 401 too, so the same assertion would still pass
		// if this path were dropped from ANONYMOUS_PATHS. Only a 200 shows the request
		// reached the controller without a token.
		assertThat(mvc.post()
			.uri("/api/auth/login")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"anon-login\",\"password\":\"correct-horse\"}")).hasStatus(HttpStatus.OK)
			.bodyJson()
			.extractingPath("$.token")
			.isNotNull();
	}

	@Test
	void signupIsAnonymousButOnlyForPost() {
		assertThat(mvc.post()
			.uri("/api/users")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"anon-signup\",\"password\":\"correct-horse\"}")).hasStatus(HttpStatus.CREATED);

		// The same path under another verb must not have been opened along with POST. The
		// GET on "/api/users" is the one that matters most — identical path, method-scoped
		// permit, so a slip from method to path would open the username lookup to anyone.
		assertThat(mvc.get().uri("/api/users?username=anon-signup")).hasStatus(HttpStatus.UNAUTHORIZED);
		assertThat(mvc.get().uri("/api/users/me")).hasStatus(HttpStatus.UNAUTHORIZED);
		assertThat(mvc.delete().uri("/api/users/1")).hasStatus(HttpStatus.UNAUTHORIZED);
		assertThat(mvc.put()
			.uri("/api/users")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{}")).hasStatus(HttpStatus.UNAUTHORIZED);
		assertThat(mvc.put()
			.uri("/api/users/1")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{}")).hasStatus(HttpStatus.UNAUTHORIZED);
	}

	/**
	 * A client that changed its own password still holds the token that change just
	 * stranded. If the chain reads that header on the way to `/api/auth/login`, the client
	 * gets `401` on the one route that could give it a working token and cannot get out
	 * without knowing to strip the header. The bearer filter runs before `permitAll`, so
	 * an anonymous route has to be reached with the header deliberately ignored.
	 */
	@Test
	void anAnonymousRouteIgnoresAStaleToken() {
		authService.signup("stranded", "correct-horse");
		String token = authService.login("stranded", "correct-horse").token();
		authService.changePassword("stranded", "me", "correct-horse", "battery-staple");

		assertThat(mvc.post()
			.uri("/api/auth/login")
			.header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"stranded\",\"password\":\"battery-staple\"}")).hasStatus(HttpStatus.OK);
	}

	@Test
	void anAnonymousRouteIgnoresAGarbageToken() {
		// A health probe that happens to carry a credential must not report an outage, and
		// signup is anonymous by method, so both have to survive an unusable header.
		assertThat(mvc.get().uri("/actuator/health").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
			.hasStatus(HttpStatus.OK);
		assertThat(mvc.get().uri("/v3/api-docs").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
			.hasStatus(HttpStatus.OK);
		assertThat(mvc.post()
			.uri("/api/users")
			.header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"header-noise\",\"password\":\"correct-horse\"}"))
			.hasStatus(HttpStatus.CREATED);
	}

	/**
	 * The other half of the rule above: ignoring the header is scoped to anonymous routes.
	 * An authenticated route must still refuse a bad token rather than fall through to
	 * anonymous access.
	 */
	@Test
	void ignoringTheHeaderDoesNotLeakIntoAuthenticatedRoutes() {
		assertThat(mvc.get().uri("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
			.hasStatus(HttpStatus.UNAUTHORIZED);
		assertThat(mvc.get().uri("/api/samples").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
			.hasStatus(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void signupCannotHandItselfTheAdminRole() {
		assertThat(mvc.post()
			.uri("/api/users")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"climber\",\"password\":\"correct-horse\",\"role\":\"ADMIN\"}"))
			.hasStatus(HttpStatus.CREATED)
			.bodyJson()
			.extractingPath("$.role")
			.isEqualTo("USER");
	}

	@Test
	void signupResponseCarriesNoPasswordField() {
		assertThat(mvc.post()
			.uri("/api/users")
			.contentType(MediaType.APPLICATION_JSON)
			.content("{\"username\":\"quiet\",\"password\":\"correct-horse\"}")).hasStatus(HttpStatus.CREATED)
			.bodyText()
			.doesNotContain("correct-horse")
			.doesNotContain("passwordHash")
			.doesNotContain("$2a$");
	}

	@Test
	void aTokenSurvivesNothingOnceTheAccountIsGone() {
		authService.signup("fleeting", "correct-horse");
		String token = authService.login("fleeting", "correct-horse").token();
		assertThat(mvc.get().uri("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
			.hasStatus(HttpStatus.OK);

		authService.delete("fleeting", "me");

		// Signature and expiry still check out; only the decoder's extra validator can
		// reject this, so a 401 here is proof that revocation is actually wired in.
		assertThat(mvc.get().uri("/api/users/me").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
			.hasStatus(HttpStatus.UNAUTHORIZED);
	}

	@Test
	void documentedAnonymousPathsStayAnonymous() {
		assertThat(mvc.get().uri("/actuator/health")).hasStatus(HttpStatus.OK);
		assertThat(mvc.get().uri("/v3/api-docs")).hasStatus(HttpStatus.OK);
		assertThat(mvc.get().uri("/swagger-ui/index.html")).hasStatus(HttpStatus.OK);

		// One per wildcard entry in ANONYMOUS_PATHS, because a `/**` that stops matching is
		// invisible from the bare path above. `/v3/api-docs/**` is the one that bites: it is
		// what Swagger UI fetches to bootstrap, so losing it breaks the UI while every other
		// case here stays green. `/swagger-ui.html` redirects rather than returning a body —
		// it is the URL the README tells people to open.
		assertThat(mvc.get().uri("/actuator/health/readiness")).hasStatus(HttpStatus.OK);
		assertThat(mvc.get().uri("/v3/api-docs/swagger-config")).hasStatus(HttpStatus.OK);
		assertThat(mvc.get().uri("/swagger-ui.html")).hasStatus(HttpStatus.FOUND);
	}


	/**
	 * The preflight is the whole reason CORS belongs in the filter chain and not in a
	 * `WebMvcConfigurer`: the browser sends `OPTIONS` with no `Authorization` header, so
	 * `anyRequest().authenticated()` answers `401` and the real request is never sent.
	 * Security's `CorsFilter` runs ahead of the authorization rules and ends the preflight
	 * there. A `200` here without a token is what proves the wiring.
	 */
	@Test
	void aPreflightFromAnAllowedOriginNeedsNoToken() {
		assertThat(mvc.options()
			.uri("/api/samples")
			.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
			.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")).hasStatus(HttpStatus.OK)
			.hasHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN);
	}

	/**
	 * `CorsConfiguration`'s permit-defaults allow `GET`, `HEAD` and `POST` only, so leaning
	 * on them leaves `PUT` and `DELETE` failing preflight while every read keeps working —
	 * a partial outage that does not look like a configuration mistake from either side.
	 * Both verbs are on the API, so both are asserted.
	 */
	@Test
	void aPreflightCoversTheWriteVerbs() {
		for (String method : new String[] { "POST", "PUT", "DELETE" }) {
			assertThat(mvc.options()
				.uri("/api/users/1")
				.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
				.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, method)).hasStatus(HttpStatus.OK)
				.hasHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN);
		}
	}

	/**
	 * The allowlist is the only thing standing between an arbitrary web page and the two
	 * anonymous routes, so an origin that is not on it has to be refused outright.
	 */
	@Test
	void aPreflightFromAnUnlistedOriginIsRefused() {
		assertThat(mvc.options()
			.uri("/api/auth/login")
			.header(HttpHeaders.ORIGIN, "https://not-invited.example.com")
			.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST")).hasStatus(HttpStatus.FORBIDDEN);
	}

	/**
	 * Passing the preflight is only half of it — the browser throws the real response away
	 * too unless that one carries the header. And CORS decides nothing about
	 * authentication: a listed origin with no token is still `401`.
	 */
	@Test
	void aCrossOriginRequestCarriesTheHeaderAndStillNeedsAToken() {
		authService.signup("cross-origin", "correct-horse");
		String token = authService.login("cross-origin", "correct-horse").token();

		assertThat(mvc.get()
			.uri("/api/samples")
			.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
			.header(HttpHeaders.AUTHORIZATION, "Bearer " + token)).hasStatus(HttpStatus.OK)
			.hasHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN);

		assertThat(mvc.get().uri("/api/samples").header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN))
			.hasStatus(HttpStatus.UNAUTHORIZED);
	}

	/**
	 * CORS is registered on `/api/**` and nowhere else, so the anonymous surfaces outside it
	 * — health and the springdoc paths — stay same-origin only. Asserted on the missing
	 * header and not on a status, because an unmapped path yields no configuration at all:
	 * the filter passes the `OPTIONS` through and MVC's own handler answers it `200`. What
	 * stops the browser is that nothing allowed the origin, not the status code.
	 */
	@Test
	void corsIsScopedToTheApi() {
		assertThat(mvc.options()
			.uri("/actuator/health")
			.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
			.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET"))
			.doesNotContainHeader(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN);
	}

}
