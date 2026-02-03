package com.grash.mapper;

import com.grash.dto.PurchaseOrderPatchDTO;
import com.grash.dto.PurchaseOrderShowDTO;
import com.grash.model.PurchaseOrder;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface PurchaseOrderMapper {
    PurchaseOrder updatePurchaseOrder(@MappingTarget PurchaseOrder entity, PurchaseOrderPatchDTO dto);

    @Mappings({})
    PurchaseOrderPatchDTO toPatchDto(PurchaseOrder model);

    PurchaseOrderShowDTO toShowDto(PurchaseOrder model);
}
