package com.grash.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class BrandConfig {
    public String name;
    public String shortName;
    public String website;
    public String mail;
    public String addressStreet;
    public String phone;
    public String addressCity;
}
