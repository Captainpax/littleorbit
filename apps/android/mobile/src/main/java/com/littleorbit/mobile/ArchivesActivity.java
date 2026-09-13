package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityArchivesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import javax.inject.Inject;
import org.json.JSONArray;

/** Read-only viewer for archives owned by the signed-in account. */
@AndroidEntryPoint
public final class ArchivesActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    private ActivityArchivesBinding binding;
    private List<ApiModels.ArchiveSummary> archives = List.of();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityArchivesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.archivePicker.setOnItemSelectedListener(new ArchiveSelection());
        AsyncUi.observe(this, orbit.archives(), binding.statusText, this::showArchives);
    }

    private void showArchives(List<ApiModels.ArchiveSummary> results) {
        archives = results;
        if (archives.isEmpty()) {
            binding.statusText.setText(R.string.no_archives);
            return;
        }
        List<String> labels = archives.stream()
                .map(item -> item.partnerDisplayName + " · " + item.endedAt)
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
        binding.archiveHeading.setText(archive.partnerDisplayName);
        binding.archiveDates.setText(archive.joinedAt + " — " + archive.endedAt);
        String content = "Notes\n" + new JSONArray(archive.notes)
                + "\n\nCountdowns\n" + new JSONArray(archive.countdowns)
                + "\n\nQuiz answers\n" + new JSONArray(archive.quizAnswers)
                + "\n\nSmooch history\n" + new JSONArray(archive.smooches);
        binding.archiveContent.setText(content);
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
