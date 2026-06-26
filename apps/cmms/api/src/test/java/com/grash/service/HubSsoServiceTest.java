package com.grash.service;

import com.grash.exception.CustomException;
import com.grash.model.OwnUser;
import com.grash.model.Role;
import com.grash.model.enums.RoleType;
import com.grash.repository.UserRepository;
import com.grash.security.JwtTokenProvider;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Collections;
import java.util.Date;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class HubSsoServiceTest {

    private static final String SECRET = "test-hub-sso-secret";
    private static final String ISSUER = "factorylm-hub";
    private static final String AUDIENCE = "atlas-cmms";

    private UserRepository userRepository;
    private JwtTokenProvider jwtTokenProvider;
    private HubSsoService service;

    @BeforeEach
    void setUp() {
        userRepository = mock(UserRepository.class);
        jwtTokenProvider = mock(JwtTokenProvider.class);
        service = new HubSsoService(userRepository, jwtTokenProvider);
        ReflectionTestUtils.setField(service, "hubSsoSecret", SECRET);
        ReflectionTestUtils.setField(service, "hubSsoIssuer", ISSUER);
        ReflectionTestUtils.setField(service, "hubSsoAudience", AUDIENCE);
    }

    @Test
    void exchangeAssertionMintsAtlasTokenForExistingEnabledUser() {
        OwnUser user = enabledClientUser("owner@example.com");
        when(userRepository.findByEmailIgnoreCase("owner@example.com")).thenReturn(Optional.of(user));
        when(jwtTokenProvider.createToken("owner@example.com", Collections.singletonList(RoleType.ROLE_CLIENT)))
                .thenReturn("atlas.jwt");

        String token = service.exchangeAssertion(validAssertion("owner@example.com"));

        assertEquals("atlas.jwt", token);
        verify(userRepository).findByEmailIgnoreCase("owner@example.com");
        verify(jwtTokenProvider).createToken("owner@example.com", Collections.singletonList(RoleType.ROLE_CLIENT));
    }

    @Test
    void exchangeAssertionRejectsUnknownUser() {
        when(userRepository.findByEmailIgnoreCase("missing@example.com")).thenReturn(Optional.empty());

        assertThrows(CustomException.class, () -> service.exchangeAssertion(validAssertion("missing@example.com")));
    }

    @Test
    void exchangeAssertionRejectsDisabledUser() {
        OwnUser user = enabledClientUser("owner@example.com");
        user.setEnabled(false);
        when(userRepository.findByEmailIgnoreCase("owner@example.com")).thenReturn(Optional.of(user));

        assertThrows(CustomException.class, () -> service.exchangeAssertion(validAssertion("owner@example.com")));
    }

    @Test
    void exchangeAssertionRejectsInvalidSignature() {
        String assertion = Jwts.builder()
                .setSubject("owner@example.com")
                .claim("email", "owner@example.com")
                .setIssuer(ISSUER)
                .setAudience(AUDIENCE)
                .setExpiration(new Date(System.currentTimeMillis() + 60000))
                .signWith(SignatureAlgorithm.HS256, "wrong-secret")
                .compact();

        assertThrows(CustomException.class, () -> service.exchangeAssertion(assertion));
        verifyNoInteractions(userRepository);
        verifyNoInteractions(jwtTokenProvider);
    }

    @Test
    void exchangeAssertionRequiresConfiguredSecret() {
        ReflectionTestUtils.setField(service, "hubSsoSecret", "");

        assertThrows(CustomException.class, () -> service.exchangeAssertion(validAssertion("owner@example.com")));
        verifyNoInteractions(userRepository);
        verifyNoInteractions(jwtTokenProvider);
    }

    private String validAssertion(String email) {
        return Jwts.builder()
                .setSubject(email)
                .claim("email", email)
                .setIssuer(ISSUER)
                .setAudience(AUDIENCE)
                .setExpiration(new Date(System.currentTimeMillis() + 60000))
                .signWith(SignatureAlgorithm.HS256, SECRET)
                .compact();
    }

    private OwnUser enabledClientUser(String email) {
        Role role = new Role();
        role.setRoleType(RoleType.ROLE_CLIENT);

        OwnUser user = new OwnUser();
        user.setEmail(email);
        user.setEnabled(true);
        user.setRole(role);
        return user;
    }
}
