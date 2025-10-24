const mongoose = require("mongoose");

const paperSchema = new mongoose.Schema({
  title: String,
  originalName: String,
  cloudinaryUrl: String,
  size: Number,
  uploadedAt: { type: Date, default: Date.now }
});


module.exports = mongoose.model("Paper", paperSchema);
