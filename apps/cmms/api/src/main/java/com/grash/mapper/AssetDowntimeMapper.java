package com.grash.mapper;

import com.grash.dto.AssetDowntimePatchDTO;
import com.grash.model.AssetDowntime;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface AssetDowntimeMapper {
    AssetDowntime updateAssetDowntime(@MappingTarget AssetDowntime entity, AssetDowntimePatchDTO dto);

    @Mappings({})
    AssetDowntimePatchDTO toPatchDto(AssetDowntime model);
}
