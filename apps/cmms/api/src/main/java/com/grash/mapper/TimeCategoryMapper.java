package com.grash.mapper;

import com.grash.dto.CategoryPatchDTO;
import com.grash.model.TimeCategory;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface TimeCategoryMapper {
    TimeCategory updateTimeCategory(@MappingTarget TimeCategory entity, CategoryPatchDTO dto);

    @Mappings({})
    CategoryPatchDTO toPatchDto(TimeCategory model);
}
