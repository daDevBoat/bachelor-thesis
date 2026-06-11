% Scatter plot from files 1.csv to 25.csv in turns_control
% Skip the first line of every CSV file
%
% X axis: absolute difference between column 3 and column 4
% Y axis: absolute difference between column 1 and column 2

folderPath = "../flight_logs/turns_control";

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

    % X axis: abs diff between column 3 and 4
    x = abs(col3 - col4);

    % Y axis: abs diff between column 1 and 2
    y = abs(col1 - col2);

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

xlabel("delta gyro magnitude");
ylabel("diff Gps and OF");
title("Absolute differences");

grid on;