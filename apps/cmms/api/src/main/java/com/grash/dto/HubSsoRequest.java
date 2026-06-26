package com.grash.dto;

import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotBlank;
import java.io.Serializable;

@Data
@NoArgsConstructor
public class HubSsoRequest implements Serializable {
    private static final long serialVersionUID = 5926468583005150708L;

    @NotBlank
    private String assertion;
}
