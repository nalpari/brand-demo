package com.eland.brand.sample;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface SampleMapper {

	int insert(Sample sample);

	Sample findById(long id);

	List<Sample> findPage(@Param("limit") int limit, @Param("afterId") long afterId);

	int updateName(@Param("id") long id, @Param("name") String name);

	int deleteById(long id);

}
