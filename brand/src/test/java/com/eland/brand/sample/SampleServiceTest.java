package com.eland.brand.sample;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@SpringBootTest
@Transactional
class SampleServiceTest {

	private static final long MISSING_ID = Long.MAX_VALUE;

	private static final int PAGE_SIZE = 50;

	@Autowired
	private SampleService service;

	@Test
	void createReturnsPersistedRow() {
		Sample created = service.create(sample("hello"));

		assertThat(created.getId()).isNotNull();
		assertThat(created.getName()).isEqualTo("hello");
		assertThat(created.getCreatedAt()).isNotNull();
		assertThat(service.findById(created.getId()).getName()).isEqualTo("hello");
	}

	@Test
	void findPageContainsCreatedRow() {
		Sample created = service.create(sample("listed"));

		assertThat(service.findPage(created.getId() - 1)).extracting(Sample::getId).contains(created.getId());
	}

	@Test
	void findPageHoldsFiftyRowsAndTheCursorAdvancesPastThem() {
		for (int i = 0; i < PAGE_SIZE + 1; i++) {
			service.create(sample("page-" + i));
		}

		List<Long> first = service.findPage(0).stream().map(Sample::getId).toList();
		List<Long> second = service.findPage(first.get(first.size() - 1)).stream().map(Sample::getId).toList();

		assertThat(first).hasSize(PAGE_SIZE);
		assertThat(second).isNotEmpty().doesNotContainAnyElementsOf(first);
	}

	@Test
	void deletingARowBeforeTheCursorDoesNotSkipTheNextPage() {
		for (int i = 0; i < PAGE_SIZE + 1; i++) {
			service.create(sample("cursor-" + i));
		}
		List<Long> first = service.findPage(0).stream().map(Sample::getId).toList();
		long cursor = first.get(first.size() - 1);
		List<Long> next = service.findPage(cursor).stream().map(Sample::getId).toList();

		assertThat(service.delete(first.get(0))).isTrue();

		assertThat(next).isNotEmpty();
		assertThat(service.findPage(cursor)).extracting(Sample::getId).containsExactlyElementsOf(next);
	}

	@Test
	void findByIdReturnsNullWhenMissing() {
		assertThat(service.findById(MISSING_ID)).isNull();
	}

	@Test
	void updateChangesName() {
		Sample created = service.create(sample("before"));
		Sample bystander = service.create(sample("bystander"));

		Sample updated = service.update(created.getId(), "after");

		assertThat(updated.getName()).isEqualTo("after");
		assertThat(updated.getCreatedAt()).isEqualTo(created.getCreatedAt());
		assertThat(service.findById(created.getId()).getName()).isEqualTo("after");
		assertThat(service.findById(bystander.getId()).getName()).isEqualTo("bystander");
	}

	@Test
	void updateReturnsNullWhenMissing() {
		assertThat(service.update(MISSING_ID, "nobody")).isNull();
	}

	@Test
	void deleteRemovesRow() {
		Sample created = service.create(sample("doomed"));
		Sample bystander = service.create(sample("bystander"));

		assertThat(service.delete(created.getId())).isTrue();
		assertThat(service.findById(created.getId())).isNull();
		assertThat(service.findById(bystander.getId())).isNotNull();
	}

	@Test
	void deleteReturnsFalseWhenMissing() {
		assertThat(service.delete(MISSING_ID)).isFalse();
	}

	@Test
	void createRejectsBlankName() {
		assertThatThrownBy(() -> service.create(sample(" "))).isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void createRejectsNulInName() {
		assertThatThrownBy(() -> service.create(sample("a\0b"))).isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void createRejectsNameLongerThanTwentyCharacters() {
		assertThat(service.create(sample("x".repeat(20))).getName()).hasSize(20);

		assertThatThrownBy(() -> service.create(sample("x".repeat(21))))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void createRejectsNameMadeOnlyOfInvisibleCharacters() {
		assertThatThrownBy(() -> service.create(sample("\u00a0\u200b\ufeff")))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	@Test
	void updateRejectsBlankName() {
		Sample created = service.create(sample("keep"));

		assertThatThrownBy(() -> service.update(created.getId(), null))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(e -> ((ResponseStatusException) e).getStatusCode())
			.isEqualTo(HttpStatus.BAD_REQUEST);
	}

	private Sample sample(String name) {
		Sample sample = new Sample();
		sample.setName(name);
		return sample;
	}

}
