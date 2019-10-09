window.onmouseover=function(){Slide(),buildSlider(),prevSlide(),nextSlide()};

var slideIndex = 0;
// Tells us which slide we are on
var currentSlideIndex = 0;
// An Array to hold all the slides
var slideArray = [];


/*-----------------------------------------------------------------
-----------------------------------------------------------------
----------------------- THE TEMPLATE ---------------------------
-----------------------------------------------------------------
-----------------------------------------------------------------*/



// Template for creating a custom Slide object
function Slide(title, subtitle, background, link ) {
    this.title = title;
    this.subtitle = subtitle;
    this.background = background;
    this.link = link;
    // we need an id to target later using getElementById
    this.id = "slide" + slideIndex;
    // Add one to the index for the next slide number
    slideIndex++;
    // Add this Slide to our array
    slideArray.push(this);
}



/*-----------------------------------------------------------------
-----------------------------------------------------------------
----------------------- SLIDE CREATION ---------------------------
-----------------------------------------------------------------
-----------------------------------------------------------------*/


// Creating our slide objects, you can make as many as you want

var walkingDead = new Slide(
    "The Walking Dead", 
    "A show about fighting zombies",
    "hotel_website/static/src/image/hotel-1.jpg",
    "hotel_website/static/src/image/hotel-2.jpg",
    "hotel_website/static/src/image/hotel-3.jpg",
);

var bigBang = new Slide(
    "The Big Bang Theory", 
    "A show about Sheldon",
    "hotel_website/static/src/image/hotel-1.jpg",
    "hotel_website/static/src/image/hotel-2.jpg",
    "hotel_website/static/src/image/hotel-3.jpg", 
);

var LastMan = new Slide(
    "The Last Man on Earth", 
    "A show about loneliness",
    "hotel_website/static/src/image/hotel-1.jpg",
    "hotel_website/static/src/image/hotel-2.jpg",
    "hotel_website/static/src/image/hotel-3.jpg", 
);



/*-----------------------------------------------------------------
-----------------------------------------------------------------
----------------------- ADD TO WEB PAGE ---------------------------
-----------------------------------------------------------------
-----------------------------------------------------------------*/



function buildSlider(){
    // A variable to hold all our HTML
    var myHTML;
    
    // Go through the Array and add the code to our HTML
    for(var i = 0; i < slideArray.length; i++) {
        
        myHTML += "<div id='" + slideArray[i].id + 
        "' class='singleSlide' style='background-image:url(" + slideArray[i].background + ");'>" + 
        "<div class='slideOverlay'>" + 
        "<h1>" + slideArray[i].title + "</h1>" +
        "<h4>" + slideArray[i].subtitle + "</h4>" +
        "<a href='" + slideArray[i].link + "' target='_blank'>Open Link</a>" +
        "</div>" +
        "</div>";   
        
    }
    
    // Print our HTML to the web page
    document.getElementById("mySlider").innerHTML = myHTML;
        
    // Display the first slide
    document.getElementById("slide" + currentSlideIndex).style.left = 0;

}

// Create our slider
buildSlider();





/*-----------------------------------------------------------------
-----------------------------------------------------------------
----------------------- SLIDER CONTROLS ---------------------------
-----------------------------------------------------------------
-----------------------------------------------------------------*/



// Navigates to the previous slide in the list
function prevSlide(){
    // Figure out what the previous slide is
    var nextSlideIndex;
    // If we are at zero go to the last slide in the list
    if (currentSlideIndex === 0 ) {
        nextSlideIndex = slideArray.length - 1;
    } else {
        // Otherwise the next one is this slide minus 1
        nextSlideIndex = currentSlideIndex - 1;
    }   
    
    // Setup the next slide and current slide for animations
    document.getElementById("slide" + nextSlideIndex).style.left = "-100%";
    document.getElementById("slide" + currentSlideIndex).style.left = 0;
    
    // Add the appropriate animation class to the slide
    document.getElementById("slide" + nextSlideIndex).setAttribute("class", "singleSlide slideInLeft");
    document.getElementById("slide" + currentSlideIndex).setAttribute("class", "singleSlide slideOutRight");
    
    // Set current slide to the new current slide
    currentSlideIndex = nextSlideIndex;
}


// Navigates to the next slide in the list
function nextSlide(){
    // Figure out what the next slide is
    var nextSlideIndex;
    // If we are at the last slide the next one is the first (zero based)
    if (currentSlideIndex === (slideArray.length - 1) ) {
        nextSlideIndex = 0;
    } else {
        // Otherwise the next slide is the current one plus 1
        nextSlideIndex = currentSlideIndex + 1;
    }   
    
    // Setup the next slide and current slide for animations
    document.getElementById("slide" + nextSlideIndex).style.left = "100%";
    document.getElementById("slide" + currentSlideIndex).style.left = 0;
    
    // Add the appropriate animation class to the slide
    document.getElementById("slide" + nextSlideIndex).setAttribute("class", "singleSlide slideInRight");
    document.getElementById("slide" + currentSlideIndex).setAttribute("class", "singleSlide slideOutLeft");
    
    // Set current slide to the new current slide
    currentSlideIndex = nextSlideIndex;
}







        
	
