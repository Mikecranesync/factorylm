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
public class PartImportDTO {

    private Long id;
    private String name;

    private double cost;

    private String category;

    private String nonStock;

    private String barcode;

    private String description;

    private double quantity;

    private String additionalInfos;

    private String area;

    private double minQuantity;

    private String locationName;
    @Builder.Default
    private Collection<String> assignedToEmails = new ArrayList<>();
    @Builder.Default
    private Collection<String> teamsNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> customersNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> vendorsNames = new ArrayList<>();
}
