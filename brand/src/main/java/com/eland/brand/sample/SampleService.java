package com.eland.brand.sample;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SampleService {

	private static final int PAGE_SIZE = 50;

	private static final int MAX_NAME_LENGTH = 20;

	private final SampleMapper mapper;

	SampleService(SampleMapper mapper) {
		this.mapper = mapper;
	}

	public List<Sample> findPage(long afterId) {
		return mapper.findPage(PAGE_SIZE, afterId);
	}

	public Sample findById(long id) {
		return mapper.findById(id);
	}

	@Transactional
	public Sample create(Sample sample) {
		requireName(sample.getName());
		if (mapper.insert(sample) != 1 || sample.getId() == null) {
			throw new IllegalStateException("insert did not create exactly one row with a generated id");
		}
		return mapper.findById(sample.getId());
	}

	@Transactional
	public Sample update(long id, String name) {
		requireName(name);
		return mapper.updateName(id, name) == 1 ? mapper.findById(id) : null;
	}

	@Transactional
	public boolean delete(long id) {
		return mapper.deleteById(id) == 1;
	}

	private void requireName(String name) {
		if (name != null && name.codePointCount(0, name.length()) > MAX_NAME_LENGTH) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
					"name must be at most " + MAX_NAME_LENGTH + " characters");
		}
		if (name == null || name.replaceAll("[\\p{Z}\\p{C}]", "").isEmpty()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "name is required");
		}
		if (name.indexOf('\0') >= 0) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "name must not contain NUL");
		}
	}

}
