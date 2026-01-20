const socket = io("http://127.0.0.1:5000");

const config = {
    type: Phaser.AUTO,
    width: 1200,
    height: 800,
    backgroundColor: '#333',
    scene: { preload: preload, create: create }
};

const game = new Phaser.Game(config);
let cardSprites = {}; // To keep track of card images on screen

function preload() {
    // We'll load actual images here later
    // For now, let's create a placeholder "card"
    this.load.image('card_back', 'https://placehold.co/63x88/blue/white?text=Card');
}

function create() {
    console.log("Phaser Scene Created");

    // Listen for the 'state_updated' event from your Python server!
    socket.on('state_updated', (data) => {
        console.log("Received update from server:", data);

        // Logic to move the card image based on data.new_zone
        handleCardMovement(data);
    });

    // Temp: Add a button to test the draw
    const drawButton = this.add.text(50, 50, 'DRAW RESEARCH', { fill: '#0f0' })
        .setInteractive()
        .on('pointerdown', () => {
            socket.emit('draw_card_request', { player_id: 1, deck_type: 'research_deck' });
        });
}

function handleCardMovement(data) {
    // This is where we will write the code to animate
    // the card from the deck to the hand/slot.
    console.log(`Animating card ${data.component_id} to ${data.new_zone}`);
}