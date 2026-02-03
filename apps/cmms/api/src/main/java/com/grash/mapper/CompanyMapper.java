package com.grash.mapper;

import com.grash.dto.CompanyPatchDTO;
import com.grash.dto.CompanyShowDTO;
import com.grash.model.Company;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring", uses = {FileMapper.class})
public interface CompanyMapper {
    Company updateCompany(@MappingTarget Company entity, CompanyPatchDTO dto);

    @Mappings({})
    CompanyPatchDTO toPatchDto(Company model);

    CompanyShowDTO toShowDto(Company model);


}
