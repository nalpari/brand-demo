package com.eland.brand.auth;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/users")
public class UserController {

	private final AuthService service;

	UserController(AuthService service) {
		this.service = service;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	@SecurityRequirements
	public User signup(@RequestBody User request) {
		return service.signup(request.getUsername(), request.getPassword());
	}

	@GetMapping
	public User findByUsername(@AuthenticationPrincipal Jwt caller, @RequestParam String username) {
		return service.findByUsername(caller.getSubject(), username);
	}

	@GetMapping("/{id}")
	public User find(@AuthenticationPrincipal Jwt caller, @PathVariable String id) {
		return service.find(caller.getSubject(), id);
	}

	@PutMapping("/{id}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void changePassword(@AuthenticationPrincipal Jwt caller, @PathVariable String id,
			@RequestBody PasswordChange change) {
		service.changePassword(caller.getSubject(), id, change.currentPassword(), change.newPassword());
	}

	@DeleteMapping("/{id}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void delete(@AuthenticationPrincipal Jwt caller, @PathVariable String id) {
		service.delete(caller.getSubject(), id);
	}

}
