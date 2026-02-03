package com.grash.repository;

import com.grash.model.Deprecation;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DeprecationRepository extends JpaRepository<Deprecation, Long> {
}
