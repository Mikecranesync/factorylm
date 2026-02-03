package com.grash.advancedsearch;

import org.springframework.data.jpa.domain.Specification;
import org.springframework.util.CollectionUtils;

import java.util.ArrayList;
import java.util.List;

public class SpecificationBuilder<T> {
    private final List<FilterField> filterFields;
    private Specification<T> andSpecification;
    private Specification<T> orSpecification;

    public SpecificationBuilder() {
        this.filterFields = new ArrayList<>();
    }

    public final SpecificationBuilder<T> with(FilterField filterField) {
        filterFields.add(filterField);
        return this;
    }

    public final SpecificationBuilder<T> with(Specification<T> specification) {
        this.andSpecification = specification;
        return this;
    }
    public final SpecificationBuilder<T> or(Specification<T> specification) {
        this.orSpecification = specification;
        return this;
    }

    public Specification<T> build() {
        if (CollectionUtils.isEmpty(filterFields) && andSpecification == null && orSpecification == null) {
            return null;
        }
        Specification<T> result = (root, query, criteriaBuilder) -> null;
        for (FilterField criteria : filterFields) {
            result = Specification.where(result).and(new WrapperSpecification<>(criteria));
        }
        if (andSpecification != null) result = result.and(andSpecification);
        if (orSpecification != null) result = result.or(orSpecification);
        return result;
    }

}
