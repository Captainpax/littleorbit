package com.littleorbit.data.repository;

import java.io.IOException;
import retrofit2.Call;
import retrofit2.Response;

/** Executes Retrofit calls through one sanitized failure boundary. */
final class RetrofitCalls {
    private RetrofitCalls() {}

    static <T> T execute(Call<T> call) {
        try {
            Response<T> response = call.execute();
            T body = response.body();
            if (!response.isSuccessful() || body == null) {
                throw new OrbitServiceException(response.code());
            }
            return body;
        } catch (IOException exception) {
            throw new OrbitServiceException(exception);
        }
    }

    static void executeVoid(Call<Void> call) {
        try {
            Response<Void> response = call.execute();
            if (!response.isSuccessful()) throw new OrbitServiceException(response.code());
        } catch (IOException exception) {
            throw new OrbitServiceException(exception);
        }
    }
}
