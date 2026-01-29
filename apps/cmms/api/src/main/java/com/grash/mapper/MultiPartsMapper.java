package com.grash.mapper;

import com.grash.dto.MultiPartsMiniDTO;
import com.grash.dto.MultiPartsPatchDTO;
import com.grash.dto.MultiPartsShowDTO;
import com.grash.model.MultiParts;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring", uses = {PartMapper.class})
public interface MultiPartsMapper {
    MultiParts updateMultiParts(@MappingTarget MultiParts entity, MultiPartsPatchDTO dto);

    @Mappings({})
    MultiPartsPatchDTO toPatchDto(MultiParts model);

    MultiPartsShowDTO toShowDto(MultiParts model);

    MultiPartsMiniDTO toMiniDto(MultiParts multiParts);
}
