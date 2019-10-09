/**
 * Variables
 */
 //website login page
window.onload=function(){
var signupButton = document.getElementById('signup-button');
var loginButton = document.getElementById('login-button');
var userForms = document.getElementById('user_options-forms');

/**
 * Add event listener to the "Sign Up" button
 */
signupButton.addEventListener('click', () => {
  userForms.classList.remove('bounceRight');
  userForms.classList.add('bounceLeft');
}, false)

/**
 * Add event listener to the "Login" button
 */
loginButton.addEventListener('click', () => {
  userForms.classList.remove('bounceLeft');
  userForms.classList.add('bounceRight');
}, false)
}


// hotel homepage roomdetail div
$(document).ready(function() {
          $('.rooms-slides .carousel .carousel-item').first().addClass('active');


$('.rooms-slides .carousel .carousel-item').each(function(){
  var next = $(this).next();
  if (!next.length) {
    next = $(this).siblings(':first');
  }
  next.children(':first-child').clone().appendTo($(this));
    for (var i=0;i<1;i++) {
    next=next.next();
    if (!next.length) {
      next = $(this).siblings(':first');
    }
    
    next.children(':first-child').clone().appendTo($(this));
  }
  
});
        });

$(document).ready(function() {
   // for room_detail image slider
    $('.container-1270px .image-and-description-with-legend-attributes-option-2 .carousel .carousel-item:eq(0)').first().addClass('active');

          $('.room-detail-slide .carousel .carousel-item').first().addClass('active');


$('.room-detail-slide .carousel .carousel-item').each(function(){
  var next = $(this).next();
  if (!next.length) {
    next = $(this).siblings(':first');
  }
  next.children(':first-child').clone().appendTo($(this));
    for (var i=0;i<1;i++) {
    next=next.next();
    if (!next.length) {
      next = $(this).siblings(':first');
    }
    
    next.children(':first-child').clone().appendTo($(this));
  }
  
});
        });

// $(document).ready(function() {
//  $('.rooms-slides .carousel .carousel-item').first().addClass('active');

//   $("quote-carousel").on("slide.bs.carousel", function(e) {
//     var $e = $(e.relatedTarget);
//     var idx = $e.index();
//     var itemsPerSlide = 3;
//     var totalItems = $(".carousel-item").length;

//     if (idx >= totalItems - (itemsPerSlide - 1)) {
//       var it = itemsPerSlide - (totalItems - idx);
//       for (var i = 0; i < it; i++) {
//         // append slides to end
//         if (e.direction == "left") {
//           $(".carousel-item")
//             .eq(i)
//             .appendTo(".carousel-inner");
//         } else {
//           $(".carousel-item")
//             .eq(0)
//             .appendTo($(this).find(".carousel-inner"));
//         }
//       }
//     }
//   });
// });



// hotel video
   $(document).ready(function() {  
     // Gets the video src from the data-src on each button    
     var $videoSrc;  
     $('.video-btn').click(function() {
       $videoSrc = $(this).data( "src" );      
     });
     //console.log($videoSrc);  
       
     // when the modal is opened autoplay it  
     $('#video_pop').on('shown.bs.modal', function (e) {
       
     // set the video src to autoplay and not to show related video. Youtube related video is like a box of chocolates... you never know what you're gonna get
     $("#video").attr('src',$videoSrc + "?rel=0&amp;showinfo=0&amp;modestbranding=1&amp;autoplay=1" ); 
     })
       // stop playing the youtube video when I close the modal
     $('#video_pop').on('hide.bs.modal', function (e) {
       $("#video").attr('src',$videoSrc); 
     }) 
   
    }); 
 // datetimepicker
$(function () {
  $('#datepickercheckin').datepicker();
});
$(function () {
  $('#datepickercheckout').datepicker();
});

// selectionfield
// $(document).ready(function() {  
// $('.selectpicker').selectpicker(
//   {  
//     liveSearchPlaceholder: 'city'
//   }
// );
// });






