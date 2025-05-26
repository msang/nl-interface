package com.example.ProsunAI;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

public class MainActivity extends AppCompatActivity {
    private RecyclerView chatRecyclerView;
    private ChatAdapter chatAdapter;
    private List<Message> messageList = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        chatRecyclerView = findViewById(R.id.chat_recycler_view);
        chatAdapter = new ChatAdapter(messageList);
        chatRecyclerView.setAdapter(chatAdapter);
        chatRecyclerView.setLayoutManager(new LinearLayoutManager(this));

        Button sendButton = findViewById(R.id.send_button);
        EditText messageInput = findViewById(R.id.message_input);

        sendButton.setOnClickListener(v -> {
            String messageText = messageInput.getText().toString();
            if (!messageText.isEmpty()) {
                sendMessageToAgent(messageText);
                messageInput.setText("");
            }
        });
    }

    private void sendMessageToAgent(String messageText) {
        // Aggiungi il messaggio dell'utente
        messageList.add(new Message(messageText, true));
        chatAdapter.notifyDataSetChanged();
        chatRecyclerView.scrollToPosition(messageList.size() - 1);

        // Invia il messaggio all'agente conversazionale
        OkHttpClient client = new OkHttpClient.Builder()
                .connectTimeout(300, TimeUnit.SECONDS) // Timeout di connessione
                .writeTimeout(300, TimeUnit.SECONDS)   // Timeout di scrittura
                .readTimeout(300, TimeUnit.SECONDS)    // Timeout di lettura
                .build();

        // Crea un oggetto JSON per il messaggio
        JSONObject json = new JSONObject();
        try {
            json.put("sender", "user"); // Identificatore dell'utente
            json.put("message", messageText); // Messaggio dell'utente
        } catch (JSONException e) {
            e.printStackTrace();
        }

        RequestBody body = RequestBody.create(
                json.toString(),
                MediaType.parse("application/json; charset=utf-8")
        );

        Request request = new Request.Builder()
                .url("https://ee22-192-84-153-19.ngrok-free.app/webhooks/rest/webhook") // Sostituisci l'URL che generi con ngrok
                .post(body)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    String responseData = response.body().string();
                    try {
                        // Analizza la risposta JSON
                        JSONArray jsonArray = new JSONArray(responseData);
                        for (int i = 0; i < jsonArray.length(); i++) {
                            JSONObject jsonObject = jsonArray.getJSONObject(i);
                            // Estrai solo il testo del messaggio
                            String text = jsonObject.getString("text");
                            // Aggiungi il messaggio dell'agente alla lista
                            runOnUiThread(() -> {
                                messageList.add(new Message(text, false));
                                chatAdapter.notifyDataSetChanged();
                                chatRecyclerView.scrollToPosition(messageList.size() - 1);
                            });
                        }
                    } catch (JSONException e) {
                        e.printStackTrace();
                    }
                } else {
                    // Gestisci l'errore di risposta
                    System.err.println("Error: " + response.code() + " " + response.message());
                }
            }

        });
    }

    // Adapter per la RecyclerView
    public class ChatAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
        private static final int VIEW_TYPE_USER = 1;
        private static final int VIEW_TYPE_AGENT = 2;
        private List<Message> messages;

        public ChatAdapter(List<Message> messages) {
            this.messages = messages;
        }

        @Override
        public int getItemViewType(int position) {
            return messages.get(position).isUser () ? VIEW_TYPE_USER : VIEW_TYPE_AGENT;
        }

        @NonNull
        @Override
        public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            if (viewType == VIEW_TYPE_USER) {
                View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_message_user, parent, false);
                return new UserViewHolder(view);
            } else {
                View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_message_agent, parent, false);
                return new AgentViewHolder(view);
            }
        }

        @Override
        public void onBindViewHolder(@NonNull RecyclerView.ViewHolder holder, int position) {
            Message message = messages.get(position);
            if (holder instanceof UserViewHolder) {
                ((UserViewHolder) holder).bind(message);
            } else {
                ((AgentViewHolder) holder).bind(message);
            }
        }

        @Override
        public int getItemCount() {
            return messages.size();
        }

        class UserViewHolder extends RecyclerView.ViewHolder {
            TextView messageText;

            UserViewHolder(View itemView) {
                super(itemView);
                messageText = itemView.findViewById(R.id.message_text);
            }

            void bind(Message message) {
                messageText.setText(message.getText());
            }
        }

        class AgentViewHolder extends RecyclerView.ViewHolder {
            TextView messageText;

            AgentViewHolder(View itemView) {
                super(itemView);
                messageText = itemView.findViewById(R.id.message_text);
            }

            void bind(Message message) {
                messageText.setText(message.getText());
            }
        }
    }


    // Classe Message
    public class Message {
        private String text;
        private boolean isUser ; // true se il messaggio è dell'utente, false se è dell'agente

        public Message(String text, boolean isUser ) {
            this.text = text;
            this.isUser  = isUser ;
        }

        public String getText() {
            return text;
        }

        public boolean isUser () {
            return isUser ;
        }
    }
}