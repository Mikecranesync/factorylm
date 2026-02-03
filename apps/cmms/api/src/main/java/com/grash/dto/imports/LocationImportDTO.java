package com.grash.dto.imports;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.Collection;

@Data
@NoArgsConstructor
@Builder
@AllArgsConstructor
public class LocationImportDTO {

    private Long id;
    private String name;

    private String address;

    private Double longitude;

    private Double latitude;

    private String parentLocationName;
    @Builder.Default
    private Collection<String> workersEmails = new ArrayList<>();
    @Builder.Default
    private Collection<String> teamsNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> customersNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> vendorsNames = new ArrayList<>();
}
