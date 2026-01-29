package com.grash.advancedsearch.pagination;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.domain.Sort.Direction;

import java.io.Serializable;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class DataTablePagination implements Serializable {
    private int page;
    private String sortField;
    private Direction sortDirection;
    private int pageSize;

    @JsonIgnore
    public static DataTablePagination paginationStreamPagination() {
        return DataTablePagination.builder().page(0).pageSize(50).sortDirection(Direction.ASC)
                .sortField("id").build();
    }

}
