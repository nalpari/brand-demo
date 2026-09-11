package com.eland.brand;

import java.nio.charset.StandardCharsets;
import java.util.List;

import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import com.eland.brand.auth.AuthService;
import com.nimbusds.jose.jwk.source.ImmutableSecret;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.server.resource.web.BearerTokenResolver;
import org.springframework.security.oauth2.server.resource.web.DefaultBearerTokenResolver;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.OrRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
public class SecurityConfig {

	private static final Logger log = LoggerFactory.getLogger(SecurityConfig.class);

	/** Name of the Swagger UI security scheme; the anonymous operations clear it. */
	public static final String BEARER_SCHEME = "bearer-jwt";

	/** HS256 refuses anything shorter, and a short secret is guessable anyway. */
	private static final int MIN_SECRET_BYTES = 32;

	/**
	 * Everything needs a bearer token except these. `/api/auth/login` is how a token is
	 * obtained, and the rest are the anonymous surfaces the docs promise:
	 * see okf/api/openapi.md and okf/api/health.md.
	 * <p>
	 * Signup is anonymous too, but it is not on this list: it is opened by method below,
	 * because a path entry here would open `GET`, `PUT` and `DELETE` on `/api/users` as
	 * well and hand every account to anonymous callers.
	 */
	private static final String[] ANONYMOUS_PATHS = { "/api/auth/login", "/actuator/health", "/actuator/health/**",
			"/v3/api-docs", "/v3/api-docs/**", "/swagger-ui.html", "/swagger-ui/**" };

	/**
	 * Every anonymous route, as one matcher. Both the authorization rules and the bearer
	 * token resolver below are built from this, because two lists of the same routes drift
	 * and the drift is silent: a route anonymous in one and not the other either `401`s
	 * where the docs promise anonymous access or reads a header it was supposed to ignore.
	 */
	private static final RequestMatcher ANONYMOUS = anonymousMatcher();

	private static RequestMatcher anonymousMatcher() {
		PathPatternRequestMatcher.Builder path = PathPatternRequestMatcher.withDefaults();
		RequestMatcher[] matchers = new RequestMatcher[ANONYMOUS_PATHS.length + 1];
		for (int i = 0; i < ANONYMOUS_PATHS.length; i++) {
			matchers[i] = path.matcher(ANONYMOUS_PATHS[i]);
		}
		// Signup, by method: see the note on ANONYMOUS_PATHS for why it is not a path entry.
		matchers[ANONYMOUS_PATHS.length] = path.matcher(HttpMethod.POST, "/api/users");
		return new OrRequestMatcher(matchers);
	}

	/**
	 * Reads the bearer token everywhere except on an anonymous route, where it returns none
	 * and leaves the request unauthenticated.
	 * <p>
	 * `BearerTokenAuthenticationFilter` runs before the authorization rules, so on any
	 * request carrying an `Authorization` header it decides the outcome first and
	 * `permitAll` is never consulted. Without this, a client whose token was just stranded
	 * by its own password change gets `401` from `/api/auth/login` — the one route that
	 * could hand it a working token — and cannot recover without knowing to strip the
	 * header. A health probe that happens to carry a stale token reports an outage for the
	 * same reason.
	 */
	private static BearerTokenResolver anonymousAwareBearerTokenResolver() {
		DefaultBearerTokenResolver delegate = new DefaultBearerTokenResolver();
		return request -> ANONYMOUS.matches(request) ? null : delegate.resolve(request);
	}

	@Bean
	SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
		return http
			// In the chain rather than in a `WebMvcConfigurer`, because Security places its
			// CorsFilter ahead of the authorization rules: a preflight `OPTIONS` carries no
			// `Authorization` header, so `anyRequest().authenticated()` would answer it with
			// `401` and the browser would never send the real request.
			.cors(Customizer.withDefaults())
			.authorizeHttpRequests(auth -> auth.requestMatchers(ANONYMOUS).permitAll().anyRequest().authenticated())
			.oauth2ResourceServer(oauth2 -> oauth2.bearerTokenResolver(anonymousAwareBearerTokenResolver())
				.jwt(Customizer.withDefaults()))
			// Bearer tokens carry the identity, so there is no session and no cookie for a
			// cross-site request to ride; CSRF protection has nothing to protect here.
			.sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
			.csrf(csrf -> csrf.disable())
			.build();
	}

	/**
	 * Describes the bearer token to springdoc. Nothing here enforces anything — it is what
	 * puts the **Authorize** button in Swagger UI and makes the UI attach the header to
	 * every operation. It lives next to the chain it describes so the two are changed
	 * together; a scheme that drifts from `ANONYMOUS_PATHS` misleads rather than helps.
	 */
	@Bean
	OpenAPI openApi() {
		return new OpenAPI()
			.components(new Components().addSecuritySchemes(BEARER_SCHEME,
					new SecurityScheme().type(SecurityScheme.Type.HTTP).scheme("bearer").bearerFormat("JWT")))
			.addSecurityItem(new SecurityRequirement().addList(BEARER_SCHEME));
	}

	/**
	 * Which browser origins may call `/api/**`, from `CORS_ALLOWED_ORIGINS` — a
	 * comma-separated list of exact origins (`https://app.example.com`). Exact, because
	 * `allowedOrigins` does not accept a wildcard subdomain and `allowedOriginPatterns`
	 * would open the API to whichever host under that domain is weakest.
	 * <p>
	 * Unset, no mapping is registered and the source answers `null` everywhere — which is
	 * what this chain did before CORS existed in it: the response carries no
	 * `Access-Control-*` header and the browser discards it. It is a property and not a
	 * constant next to {@code ANONYMOUS_PATHS} because the origins differ per environment
	 * and must not need a rebuild. `@Value` into a `List<String>` is the comma split and the
	 * trim, so there is no parsing here to get wrong.
	 * <p>
	 * Credentials stay off. The token rides an `Authorization` header, so nothing needs a
	 * cookie to cross origins — and `allowCredentials` is exactly what would reopen the CSRF
	 * question that the stateless header settles.
	 */
	@Bean
	CorsConfigurationSource corsConfigurationSource(@Value("${cors.allowed-origins:}") List<String> allowedOrigins) {
		UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
		if (allowedOrigins.isEmpty()) {
			return source;
		}
		CorsConfiguration config = new CorsConfiguration();
		config.setAllowedOrigins(allowedOrigins);
		// Spelled out rather than left to applyPermitDefaultValues(), which permits GET, HEAD
		// and POST only: the API's PUT and DELETE would fail preflight while every read kept
		// working, and a half-working API does not look like a CORS mistake from either side.
		config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
		// Request headers are not a boundary here — the server ignores what it does not read,
		// and with credentials off nothing rides along to protect. `Authorization` and
		// `Content-Type` are the two that actually arrive.
		config.setAllowedHeaders(List.of("*"));
		// Unset, a browser caches the preflight for seconds and every write costs two round
		// trips.
		config.setMaxAge(3600L);
		source.registerCorsConfiguration("/api/**", config);
		return source;
	}

	@Bean
	PasswordEncoder passwordEncoder() {
		return new BCryptPasswordEncoder();
	}

	/**
	 * The HMAC key that signs and verifies tokens, from `JWT_SECRET`. When it is unset a
	 * random key is generated instead, so a developer can boot without ceremony — at the
	 * cost of every token dying with the process and no two instances agreeing. That is
	 * deliberate: a default secret checked into this repository would sign production
	 * tokens for anyone who cloned it.
	 */
	@Bean
	SecretKey jwtSecretKey(@Value("${jwt.secret:}") String secret) throws Exception {
		if (secret.isBlank()) {
			log.warn("JWT_SECRET is not set — signing with a random key. "
					+ "Tokens will not survive a restart and will not verify on another instance.");
			return KeyGenerator.getInstance("HmacSHA256").generateKey();
		}
		byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
		if (bytes.length < MIN_SECRET_BYTES) {
			throw new IllegalStateException(
					"JWT_SECRET must be at least " + MIN_SECRET_BYTES + " bytes, got " + bytes.length);
		}
		return new SecretKeySpec(bytes, "HmacSHA256");
	}

	/**
	 * Signature and expiry are Nimbus's job; the extra validator is what makes a password
	 * change or a deleted account take effect before the hour is up. It costs one `users`
	 * read per authenticated request — the price of revoking a stateless token.
	 */
	@Bean
	JwtDecoder jwtDecoder(SecretKey key, AuthService accounts) {
		NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(key).build();
		decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(JwtValidators.createDefault(),
				jwt -> isStale(accounts, jwt)
						? OAuth2TokenValidatorResult
							.failure(new OAuth2Error("invalid_token", "the account changed after this token was issued", null))
						: OAuth2TokenValidatorResult.success()));
		return decoder;
	}

	/**
	 * Fails closed when the account cannot be read. A `DataAccessException` is not a
	 * `JwtException`, and `JwtAuthenticationProvider` translates only the latter — so an
	 * unreachable database would otherwise propagate out of the bearer filter and answer
	 * every authenticated request with `500` and a stack trace rather than something inside
	 * the security contract. Treating it as stale is the safe direction: the token is
	 * refused rather than accepted on a check that did not run. The API is unusable during
	 * such an outage either way, since every endpoint behind it needs the same database.
	 */
	private static boolean isStale(AuthService accounts, org.springframework.security.oauth2.jwt.Jwt jwt) {
		try {
			return accounts.isTokenStale(jwt.getSubject(), jwt.getIssuedAt());
		}
		catch (DataAccessException ex) {
			log.error("Could not check token staleness; refusing the token", ex);
			return true;
		}
	}

	@Bean
	JwtEncoder jwtEncoder(SecretKey key) {
		return new NimbusJwtEncoder(new ImmutableSecret<>(key));
	}

}
