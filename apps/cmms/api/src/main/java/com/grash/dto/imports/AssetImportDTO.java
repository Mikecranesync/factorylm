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
public class AssetImportDTO {

    private Long id;
    private String archived;
    private String description;

    private String locationName;

    private String parentAssetName;

    private String area;

    private String barCode;

    private String category;

    private String name;

    private String primaryUserEmail;


    private Double warrantyExpirationDate;

    private String additionalInfos;

    private String serialNumber;
    @Builder.Default
    private Collection<String> assignedToEmails = new ArrayList<>();
    @Builder.Default
    private Collection<String> teamsNames = new ArrayList<>();

    private String status;

    private Double acquisitionCost;
    @Builder.Default
    private Collection<String> customersNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> vendorsNames = new ArrayList<>();
    @Builder.Default
    private Collection<String> partsNames = new ArrayList<>();
    private String model;
    private String manufacturer;
    private String power;
}
