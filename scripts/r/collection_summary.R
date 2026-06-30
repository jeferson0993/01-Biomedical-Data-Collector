#!/usr/bin/env Rscript

library(optparse)
library(dplyr)
library(ggplot2)
library(jsonlite)

option_list <- list(
  make_option("--collection_id", type = "character", help = "Collection UUID"),
  make_option("--metadata", type = "character", help = "Path to collection metadata JSON"),
  make_option("--outdir", type = "character", default = ".", help = "Output directory")
)
opt <- parse_args(OptionParser(option_list = option_list))

dir.create(opt$outdir, showWarnings = FALSE, recursive = TRUE)

meta <- fromJSON(opt$metadata, simplifyVector = TRUE)

source_dist <- as.data.frame(table(meta$source))
colnames(source_dist) <- c("source", "count")

df <- meta$datasets
if (is.null(df) || nrow(df) == 0) {
  df <- data.frame(filename = character(), file_size = numeric(), format = character())
}

summary_stats <- data.frame(
  metric = c(
    "collection_id", "source", "status", "total_datasets",
    "total_size_bytes", "avg_file_size", "median_file_size",
    "unique_formats", "created_at"
  ),
  value = c(
    opt$collection_id,
    ifelse(is.null(meta$source), "N/A", meta$source),
    ifelse(is.null(meta$status), "N/A", meta$status),
    nrow(df),
    sum(df$file_size, na.rm = TRUE),
    round(mean(df$file_size, na.rm = TRUE), 0),
    round(median(df$file_size, na.rm = TRUE), 0),
    n_distinct(df$format),
    ifelse(is.null(meta$created_at), "N/A", meta$created_at)
  )
)
write.csv(summary_stats, file.path(opt$outdir, "collection_summary.csv"), row.names = FALSE)

if (nrow(source_dist) > 0) {
  p_src <- ggplot(source_dist, aes(x = source, y = count, fill = source)) +
    geom_bar(stat = "identity") +
    labs(title = "Datasets per Source", x = "Source", y = "Count") +
    theme_minimal() + theme(legend.position = "none")
  ggsave(file.path(opt$outdir, "source_dist.png"), p_src, width = 6, height = 4)
}

if (nrow(df) > 0 && sum(df$file_size > 0, na.rm = TRUE) > 0) {
  p_size <- ggplot(df, aes(x = file_size / 1024)) +
    geom_histogram(bins = 30, fill = "#2563eb", alpha = 0.8) +
    scale_x_log10(labels = scales::comma) +
    labs(title = "File Size Distribution", x = "Size (KB, log10)", y = "Count") +
    theme_minimal()
  ggsave(file.path(opt$outdir, "file_size_dist.png"), p_size, width = 8, height = 5)
}

if (nrow(df) > 0) {
  fmt_dist <- as.data.frame(table(df$format))
  colnames(fmt_dist) <- c("format", "count")
  p_fmt <- ggplot(fmt_dist, aes(x = format, y = count, fill = format)) +
    geom_bar(stat = "identity") +
    labs(title = "Datasets per Format", x = "Format", y = "Count") +
    theme_minimal() + theme(legend.position = "none")
  ggsave(file.path(opt$outdir, "format_dist.png"), p_fmt, width = 6, height = 4)
}

cat(sprintf("Collection summary generated for %s\n", opt$collection_id))
