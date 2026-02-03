package com.grash.mapper;

import com.grash.dto.CurrencyPatchDTO;
import com.grash.model.Currency;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface CurrencyMapper {
    Currency updateCurrency(@MappingTarget Currency entity, CurrencyPatchDTO dto);

    @Mappings({})
    CurrencyPatchDTO toPatchDto(Currency model);
}
