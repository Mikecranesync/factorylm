package com.grash.repository;

import com.grash.model.AdditionalCost;
import com.grash.model.SuperAccountRelation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;

public interface SuperAccountRelationRepository extends JpaRepository<SuperAccountRelation, Long> {
    SuperAccountRelation findBySuperUser_IdAndChildUser_Id(Long superUserId, Long childUserId);
}
