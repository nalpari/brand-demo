package com.eland.brand;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;

import tools.jackson.core.StreamReadConstraints;
import tools.jackson.core.json.JsonFactory;
import tools.jackson.databind.json.JsonMapper;

@SpringBootApplication
public class BrandApplication {

	private static final long MAX_REQUEST_BODY_BYTES = 8 * 1024;

	public static void main(String[] args) {
		SpringApplication.run(BrandApplication.class, args);
	}

	/**
	 * Caps the request body Jackson will parse. Jackson's own defaults are
	 * {@code maxDocumentLength} unlimited and {@code maxStringLength} 100M characters, so
	 * without this one anonymous POST can drive ~200MB of heap for a single `name` before
	 * {@code SampleService} ever sees it and rejects it. The cap belongs at the parser
	 * rather than in a {@code Content-Length} filter because it also holds for chunked
	 * requests, which carry no length to check.
	 * <p>
	 * This restates {@code JacksonAutoConfiguration#jsonMapperBuilder} because
	 * {@code JsonMapper.Builder} takes its factory at construction and exposes no setter,
	 * so a {@link JsonMapperBuilderCustomizer} cannot reach it. Boot's own customizers are
	 * still applied, so {@code spring.jackson.*} and the problem-detail mixins survive.
	 */
	@Bean
	JsonMapper.Builder jsonMapperBuilder(ObjectProvider<JsonMapperBuilderCustomizer> customizers) {
		JsonFactory factory = JsonFactory.builder()
			.streamReadConstraints(
					StreamReadConstraints.builder().maxDocumentLength(MAX_REQUEST_BODY_BYTES).build())
			.build();
		JsonMapper.Builder builder = JsonMapper.builder(factory);
		customizers.orderedStream().forEach(customizer -> customizer.customize(builder));
		return builder;
	}

}
