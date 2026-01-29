package com.grash.dto.imports;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.Collection;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MeterImportDTO {

    private Long id;

    private String name;

    private String unit;

    private int updateFrequency;

    private String meterCategory;

    private String locationName;
    private String assetName;
    @Builder.Default
    private Collection<String> usersEmails = new ArrayList<>();
}
