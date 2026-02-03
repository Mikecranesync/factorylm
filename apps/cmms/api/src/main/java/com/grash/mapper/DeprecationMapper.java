package com.grash.mapper;

import com.grash.dto.DeprecationPatchDTO;
import com.grash.model.Deprecation;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface DeprecationMapper {
    Deprecation updateDeprecation(@MappingTarget Deprecation entity, DeprecationPatchDTO dto);

    @Mappings({})
    DeprecationPatchDTO toPatchDto(Deprecation model);
}
