package com.grash.model.enums;

import org.springframework.security.core.GrantedAuthority;

public enum RoleType implements GrantedAuthority {
    ROLE_SUPER_ADMIN,
    ROLE_CLIENT;

    public String getAuthority() {
        return name();
    }
}
