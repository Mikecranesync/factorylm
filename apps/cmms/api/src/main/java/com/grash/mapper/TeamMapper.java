package com.grash.mapper;

import com.grash.dto.TeamMiniDTO;
import com.grash.dto.TeamPatchDTO;
import com.grash.dto.TeamShowDTO;
import com.grash.model.Team;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring", uses = {UserMapper.class})
public interface TeamMapper {
    Team updateTeam(@MappingTarget Team entity, TeamPatchDTO dto);

    @Mappings({})
    TeamPatchDTO toPatchDto(Team model);

    TeamMiniDTO toMiniDto(Team model);

    TeamShowDTO toShowDto(Team model);
}
