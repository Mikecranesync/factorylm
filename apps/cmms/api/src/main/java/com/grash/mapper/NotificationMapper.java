package com.grash.mapper;

import com.grash.dto.NotificationPatchDTO;
import com.grash.model.Notification;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface NotificationMapper {
    Notification updateNotification(@MappingTarget Notification entity, NotificationPatchDTO dto);

    @Mappings({})
    NotificationPatchDTO toPatchDto(Notification model);
}
