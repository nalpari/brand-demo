package com.eland.brand.sample;

import java.util.List;
import java.util.Optional;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/samples")
public class SampleController {

	private final SampleService service;

	SampleController(SampleService service) {
		this.service = service;
	}

	@GetMapping
	public List<Sample> findPage(@RequestParam(defaultValue = "0") long afterId) {
		return service.findPage(afterId);
	}

	@GetMapping("/{id}")
	public ResponseEntity<Sample> findById(@PathVariable long id) {
		return ResponseEntity.of(Optional.ofNullable(service.findById(id)));
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public Sample create(@RequestBody Sample sample) {
		return service.create(sample);
	}

	@PutMapping("/{id}")
	public ResponseEntity<Sample> update(@PathVariable long id, @RequestBody Sample sample) {
		return ResponseEntity.of(Optional.ofNullable(service.update(id, sample.getName())));
	}

	@DeleteMapping("/{id}")
	public ResponseEntity<Void> delete(@PathVariable long id) {
		return service.delete(id) ? ResponseEntity.noContent().build() : ResponseEntity.notFound().build();
	}

}
