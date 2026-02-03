package com.grash.mapper;

import com.grash.dto.SchedulePatchDTO;
import com.grash.model.Schedule;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface ScheduleMapper {
    Schedule updateSchedule(@MappingTarget Schedule entity, SchedulePatchDTO dto);

    @Mappings({})
    SchedulePatchDTO toPatchDto(Schedule model);
}
