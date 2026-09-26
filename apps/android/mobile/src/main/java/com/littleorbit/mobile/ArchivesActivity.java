package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityArchivesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.format.FormatStyle;
import javax.inject.Inject;

/** Read-only viewer for archives owned by the signed-in account. */
@AndroidEntryPoint
public final class ArchivesActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    private ActivityArchivesBinding binding;
    private List<ApiModels.ArchiveSummary> archives = List.of();
    private ArchiveContentView content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityArchivesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        content = new ArchiveContentView(this, orbit, binding.archiveContent, binding.statusText);
        binding.archivePicker.setOnItemSelectedListener(new ArchiveSelection());
        AsyncUi.observe(this, orbit.archives(), binding.statusText, this::showArchives);
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.ARCHIVES;
    }

    private void showArchives(List<ApiModels.ArchiveSummary> results) {
        archives = results;
        boolean available = !archives.isEmpty();
        binding.archivePickerLabel.setVisibility(available ? View.VISIBLE : View.GONE);
        binding.archivePicker.setVisibility(available ? View.VISIBLE : View.GONE);
        binding.archiveHeading.setVisibility(View.GONE);
        binding.archiveDates.setVisibility(View.GONE);
        binding.archiveContent.setVisibility(View.GONE);
        if (archives.isEmpty()) {
            binding.statusText.setText(R.string.no_archives);
            return;
        }
        List<String> labels = archives.stream()
                .map(item -> getString(
                        R.string.visual_archive_picker_row,
                        item.partnerDisplayName,
                        displayDate(item.endedAt)))
                .collect(java.util.stream.Collectors.toList());
        binding.archivePicker.setAdapter(new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_dropdown_item, labels));
    }

    private void loadArchive(int position) {
        if (position < 0 || position >= archives.size()) {
            return;
        }
        AsyncUi.observe(
                this,
                orbit.archive(archives.get(position).archiveId),
                binding.statusText,
                this::showArchive);
    }

    private void showArchive(ApiModels.ArchiveDetail archive) {
        binding.archiveHeading.setVisibility(View.VISIBLE);
        binding.archiveDates.setVisibility(View.VISIBLE);
        binding.archiveContent.setVisibility(View.VISIBLE);
        binding.archiveHeading.setText(archive.partnerDisplayName);
        binding.archiveDates.setText(getString(
                R.string.archive_dates,
                displayDate(archive.joinedAt),
                displayDate(archive.endedAt)));
        content.show(archive);
    }

    private String displayDate(String value) {
        try {
            return OffsetDateTime.parse(value).format(DateTimeFormatter.ofLocalizedDate(
                    FormatStyle.MEDIUM).withLocale(getResources().getConfiguration().getLocales().get(0)));
        } catch (DateTimeParseException ignored) {
            return value;
        }
    }

    private final class ArchiveSelection implements AdapterView.OnItemSelectedListener {
        @Override
        public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
            loadArchive(position);
        }

        @Override
        public void onNothingSelected(AdapterView<?> parent) {
            // An empty archive list has no detail request.
        }
    }
}
