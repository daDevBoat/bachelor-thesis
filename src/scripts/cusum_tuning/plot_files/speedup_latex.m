%% speedup_only_latex_tables.m
% Outputs speedup factors as LaTeX tables.
%
% Table 1:
%   SSDGOF vs Standard CUSUM
%   Includes straight path.
%
% Table 2:
%   Standard CUSUM vs Adaptive CUSUM^2
%   Excludes straight path.
%
% Speedup factor:
%   speedup = old_method_time / new_method_time
%
% A speedup above 1 means the second method is faster.
%
% The "Average across all runs" value accounts for N because it pools all
% valid paired runs before calculating the speedup.

clear; clc; close all;

%% CSV files
csvDir = 'csv_run_files';

filesAll = {
    fullfile(csvDir, 'straight_spoofed_25.csv')
    fullfile(csvDir, 'turns_spoofed_100.csv')
    fullfile(csvDir, 'turns_spoofed_140.csv')
    fullfile(csvDir, 'turns_spoofed_275.csv')
    fullfile(csvDir, 'blind_spoofed_65.csv')
    fullfile(csvDir, 'blind_spoofed_160.csv')
};

flightPathsAll = {
    'Straight path'
    'Path with multiple $90^\circ$ turns'
    'Path with multiple $90^\circ$ turns'
    'Path with multiple $90^\circ$ turns'
    'Blind path'
    'Blind path'
};

%% Table 1: SSDGOF vs Standard CUSUM, including straight path
latexTable1 = makeSpeedupOnlyTable( ...
    filesAll, ...
    flightPathsAll, ...
    'SSDGOF_time', ...
    'CUSUM_time', ...
    'Speedup from SSDGOF to standard CUSUM', ...
    'tab:ssdgof_to_cusum_speedup', ...
    true ...
);

%% Table 2: Standard CUSUM vs Adaptive CUSUM^2, excluding straight path
filesNoStraight = filesAll(2:end);
flightPathsNoStraight = flightPathsAll(2:end);

latexTable2 = makeSpeedupOnlyTable( ...
    filesNoStraight, ...
    flightPathsNoStraight, ...
    'CUSUM_time', ...
    'adapt_CUSUM_time', ...
    'Speedup from standard CUSUM to adaptive CUSUM$^2$', ...
    'tab:cusum_to_adaptive_cusum2_speedup', ...
    false ...
);

%% Print copyable LaTeX tables
fprintf('\n===== SSDGOF VS STANDARD CUSUM =====\n\n');
fprintf('%s\n', latexTable1);

fprintf('\n===== STANDARD CUSUM VS ADAPTIVE CUSUM^2, NO STRAIGHT PATH =====\n\n');
fprintf('%s\n', latexTable2);

%% Save LaTeX tables
writeTextFile('table_ssdgof_to_cusum_speedup_only.tex', latexTable1);
writeTextFile('table_cusum_to_adaptive_cusum2_speedup_no_straight.tex', latexTable2);

%% Copy both tables to clipboard if possible
try
    clipboard('copy', sprintf('%s\n\n%s', latexTable1, latexTable2));
    fprintf('\nBoth LaTeX tables were copied to the clipboard.\n');
catch
    fprintf('\nTables were printed and saved, but clipboard copy failed.\n');
end

%% Function: Make speedup-only LaTeX table
function latexTable = makeSpeedupOnlyTable(files, flightPaths, oldColName, newColName, captionText, labelText, addMissingNote)

    nPaths = numel(files);
    speedupFactor = nan(nPaths, 1);

    allOldVals = [];
    allNewVals = [];

    hasMissingSpeedup = false;

    for i = 1:nPaths
        T = readtable(files{i});

        oldVals = toNumericVector(T.(oldColName));
        newVals = toNumericVector(T.(newColName));

        % Use only paired valid detections
        valid = ~isnan(oldVals) & ~isnan(newVals) & oldVals > 0 & newVals > 0;

        oldPaired = oldVals(valid);
        newPaired = newVals(valid);

        if ~isempty(oldPaired)
            % Per-path speedup
            speedupFactor(i) = mean(oldPaired) / mean(newPaired);

            % Store every valid paired run for N-weighted overall speedup
            allOldVals = [allOldVals; oldPaired];
            allNewVals = [allNewVals; newPaired];
        else
            hasMissingSpeedup = true;
        end
    end

    %% Average across all runs, taking N into account
    if isempty(allOldVals)
        overallSpeedup = nan;
    else
        overallSpeedup = mean(allOldVals) / mean(allNewVals);
    end

    %% Build LaTeX table
    latexTable = "";
    latexTable = latexTable + "\begin{table}[!ht]" + newline;
    latexTable = latexTable + "\centering" + newline;
    latexTable = latexTable + "\scriptsize" + newline;
    latexTable = latexTable + "\caption{" + captionText + "}" + newline;
    latexTable = latexTable + "\label{" + labelText + "}" + newline;
    latexTable = latexTable + "\begin{tabular}{|p{0.42\textwidth}|c|}" + newline;
    latexTable = latexTable + "\hline" + newline;
    latexTable = latexTable + "\textbf{Flight path} & \textbf{Speedup factor} \\" + newline;
    latexTable = latexTable + "\hline" + newline;

    for i = 1:nPaths
        if isnan(speedupFactor(i))
            if addMissingNote
                speedupText = "--$^{*}$";
            else
                speedupText = "--";
            end
        else
            speedupText = sprintf('%.3f$\\times$', speedupFactor(i));
        end

        latexTable = latexTable + sprintf( ...
            '%s & %s \\\\%s', ...
            flightPaths{i}, ...
            speedupText, ...
            newline ...
        );

        latexTable = latexTable + "\hline" + newline;
    end

    if isnan(overallSpeedup)
        overallText = "--";
    else
        overallText = sprintf('\\textbf{%.3f$\\times$}', overallSpeedup);
    end

    latexTable = latexTable + sprintf( ...
        '\\textbf{Average across all runs} & %s \\\\%s', ...
        overallText, ...
        newline ...
    );

    latexTable = latexTable + "\hline" + newline;
    latexTable = latexTable + "\end{tabular}" + newline;

    if addMissingNote && hasMissingSpeedup
        latexTable = latexTable + newline;
        latexTable = latexTable + "\vspace{0.5em}" + newline;
        latexTable = latexTable + "\raggedright" + newline;
        latexTable = latexTable + "\scriptsize{$^{*}$No speedup factor is reported because SSDGOF did not detect spoofing in any runs.}" + newline;
    end

    latexTable = latexTable + "\end{table}" + newline;
end

%% Helper function
function vals = toNumericVector(x)
    if isnumeric(x)
        vals = x;
    elseif iscell(x)
        vals = str2double(x);
    elseif iscategorical(x)
        vals = str2double(cellstr(x));
    else
        vals = str2double(cellstr(string(x)));
    end

    vals = vals(:);
end

%% Write text file
function writeTextFile(filename, textContent)
    fid = fopen(filename, 'w');

    if fid == -1
        error('Could not open file for writing: %s', filename);
    end

    fprintf(fid, '%s', textContent);
    fclose(fid);
end