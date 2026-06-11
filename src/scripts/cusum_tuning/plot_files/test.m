% Scatter plot from files 1.csv to 25.csv in turns_control
% Skip the first line of every CSV file
%
% X axis: sliding-window sum of abs(column 3 - column 4)
% Y axis: abs(column 1 - column 2)

folderPath = "../flight_logs/turns_control";

windowSize = 25;

allX = [];
allY = [];

for fileNum = 1:25
    filename = fullfile(folderPath, sprintf("%d.csv", fileNum));

    if ~isfile(filename)
        warning("Skipping %s: file does not exist.", filename);
        continue;
    end

    % Read CSV data
    data = readmatrix(filename);

    % Skip first row
    data = data(2:end, :);

    % Check that the file has at least 4 columns
    if size(data, 2) < 4
        warning("Skipping %s: file has fewer than 4 columns.", filename);
        continue;
    end

    % Read needed columns
    col1 = data(:, 1);
    col2 = data(:, 2);
    col3 = data(:, 3);
    col4 = data(:, 4);

    % Remove rows with NaN values
    validRows = ~isnan(col1) & ~isnan(col2) & ~isnan(col3) & ~isnan(col4);

    col1 = col1(validRows);
    col2 = col2(validRows);
    col3 = col3(validRows);
    col4 = col4(validRows);

    % Base differences
    xDiff = abs(col3 - col4);
    yDiff = abs(col1 - col2);

    % Skip files with fewer than 25 valid rows
    if length(xDiff) < windowSize
        warning("Skipping %s: fewer than %d valid rows.", filename, windowSize);
        continue;
    end

    % X: sliding-window sum over 25 consecutive values
    x = conv(xDiff, ones(windowSize, 1), "valid");

    % Y: keep as normal abs diff
    % Match Y with the END of each 25-sample x window
    y = yDiff(windowSize:end);

    % Store all points from all files
    allX = [allX; x];
    allY = [allY; y];
end

if isempty(allX)
    error("No valid data was found in the CSV files.");
end

% Create scatter plot
figure;
scatter(allX, allY, 15, "filled");

xlabel("25-sample window sum of delta gyro magnitude");
ylabel("|Column 1 - Column 2|");
title("Sliding-window gyro sum vs diff GPS and OF");

grid on;