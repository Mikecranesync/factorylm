package com.grash.mapper;

import com.grash.dto.CategoryPatchDTO;
import com.grash.model.AssetCategory;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface AssetCategoryMapper {
    AssetCategory updateAssetCategory(@MappingTarget AssetCategory entity, CategoryPatchDTO dto);

    @Mappings({})
    CategoryPatchDTO toPatchDto(AssetCategory model);
}
