package com.grash.mapper;

import com.grash.dto.SubscriptionPlanPatchDTO;
import com.grash.model.SubscriptionPlan;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface SubscriptionPlanMapper {
    SubscriptionPlan updateSubscriptionPlan(@MappingTarget SubscriptionPlan entity, SubscriptionPlanPatchDTO dto);

    @Mappings({})
    SubscriptionPlanPatchDTO toPatchDto(SubscriptionPlan model);
}
