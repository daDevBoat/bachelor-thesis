%% cusum_speedup_factor_no_straight.m
% Calculates speedup factor between Standard CUSUM and Adaptive CUSUM^2.
%
% Straight path is excluded.
%
% Speedup factor:
%   speedup = mean_Standard_CUSUM_time / mean_Adaptive_CUSUM2_time
%
% If speedup > 1, Adaptive CUSUM^2 is faster.
% If speedup = 1, they are equally fast.
% If speedup < 1, Adaptive CUSUM^2 is slower.

clear; clc; close all;

%% CSV files and labels
csvDir = 'csv_run_files';

% Exclude straight path
files = {
    fullfile(csvDir, 'turns_spoofed_100.csv')
    fullfile(csvDir, 'turns_spoofed_140.csv')
    fullfile(csvDir, 'turns_spoofed_275.csv')
    fullfile(csvDir, 'blind_spoofed_65.csv')
    fullfile(csvDir, 'blind_spoofed_160.csv')
};

pathLabels = {
    'turns spoofed 100'
    'turns spoofed 140'
    'turns spoofed 275'
    'blind spoofed 65'
    'blind spoofed 160'
};

%% Allocate storage
nPaths = numel(files);

meanStandardCUSUM = nan(nPaths, 1);
meanAdaptiveCUSUM2 = nan(nPaths, 1);

speedupFactor = nan(nPaths, 1);

countStandardCUSUM = zeros(nPaths, 1);
countAdaptiveCUSUM2 = zeros(nPaths, 1);

%% Calculate speedup factor per path
for i = 1:nPaths
    T = readtable(files{i});

    standardVals = toNumericVector(T.CUSUM_time);
    adaptiveVals = toNumericVector(T.adapt_CUSUM_time);

    % Ignore missing / NaN values
    standardVals = standardVals(~isnan(standardVals));
    adaptiveVals = adaptiveVals(~isnan(adaptiveVals));

    countStandardCUSUM(i) = numel(standardVals);
    countAdaptiveCUSUM2(i) = numel(adaptiveVals);

    if ~isempty(standardVals)
        meanStandardCUSUM(i) = mean(standardVals);
    end

    if ~isempty(adaptiveVals)
        meanAdaptiveCUSUM2(i) = mean(adaptiveVals);
    end

    if ~isnan(meanStandardCUSUM(i)) && ...
       ~isnan(meanAdaptiveCUSUM2(i)) && ...
       meanAdaptiveCUSUM2(i) > 0

        speedupFactor(i) = meanStandardCUSUM(i) / meanAdaptiveCUSUM2(i);
    end
end

%% Total speedup factor
validRows = ~isnan(speedupFactor);

totalStandardCUSUMTime = sum(meanStandardCUSUM(validRows));
totalAdaptiveCUSUM2Time = sum(meanAdaptiveCUSUM2(validRows));

totalSpeedupFactor = totalStandardCUSUMTime / totalAdaptiveCUSUM2Time;

%% Average speedup factor
averageSpeedupFactor = mean(speedupFactor(validRows));

%% Results table
resultsTable = table( ...
    pathLabels(:), ...
    countStandardCUSUM, ...
    countAdaptiveCUSUM2, ...
    meanStandardCUSUM, ...
    meanAdaptiveCUSUM2, ...
    speedupFactor, ...
    'VariableNames', { ...
        'Path', ...
        'Standard_CUSUM_n', ...
        'Adaptive_CUSUM2_n', ...
        'Mean_Standard_CUSUM_time_s', ...
        'Mean_Adaptive_CUSUM2_time_s', ...
        'Speedup_factor' ...
    } ...
);

disp('Per-path speedup factor:');
disp(resultsTable);

fprintf('\n===== SPEEDUP SUMMARY =====\n');
fprintf('Average speedup factor: %.3fx\n', averageSpeedupFactor);
fprintf('Total speedup factor: %.3fx\n', totalSpeedupFactor);

%% Save results
writetable(resultsTable, 'CUSUM_vs_Adaptive_CUSUM2_speedup_factor_no_straight.csv');

fprintf('\nSaved file:\n');
fprintf('  CUSUM_vs_Adaptive_CUSUM2_speedup_factor_no_straight.csv\n');

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